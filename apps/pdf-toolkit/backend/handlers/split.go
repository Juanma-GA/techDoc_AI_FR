package handlers

import (
	"archive/zip"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"mime"
	"net"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"

	"github.com/gin-gonic/gin"

	"pdf-toolkit/services"
)

const defaultSplitFolder = "split"
const splitProgressIDHeader = "X-Split-Progress-ID"
const directSplitExportHeader = "X-PDF-Toolkit-Direct-Export"

func (h *PDFHandler) Split(c *gin.Context) {
	progressID := c.GetHeader(splitProgressIDHeader)
	if progressID != "" {
		if !isSplitProgressID(progressID) {
			writeError(c, http.StatusBadRequest, "L’identifiant de progression est invalide.")
			return
		}
		if !h.splitProgress.start(progressID) {
			writeError(c, http.StatusConflict, "Cette progression est déjà utilisée.")
			return
		}
		defer h.splitProgress.remove(progressID)
		h.splitProgress.update(progressID, "processing", 0, 0)
	}

	tempDir, ok := createWorkspace(c)
	if !ok {
		return
	}
	defer removeWorkspace(tempDir)

	upload, err := parseMultipart(c.Request, tempDir, "file", 1, "groups", "folder", "zip_path")
	if err != nil {
		writeUploadError(c, err)
		return
	}
	if len(upload.files) != 1 {
		writeError(c, http.StatusBadRequest, "Sélectionnez un fichier PDF.")
		return
	}
	rawGroups, err := singleField(upload.fields, "groups")
	if err != nil {
		writeUploadError(c, err)
		return
	}
	var groups []services.SplitGroup
	if err := json.Unmarshal([]byte(rawGroups), &groups); err != nil || len(groups) == 0 {
		writeError(c, http.StatusBadRequest, "La liste des documents à générer est invalide.")
		return
	}
	if len(groups) > services.MaxSplitGroups {
		writeError(c, http.StatusBadRequest, "Le découpage dépasse le nombre maximal de documents.")
		return
	}
	rawFolder, err := optionalSingleField(upload.fields, "folder")
	if err != nil {
		writeUploadError(c, err)
		return
	}
	folder := services.SanitizeSplitBaseName(rawFolder)
	if folder == "" {
		folder = defaultSplitFolder
	}

	outputDir := filepath.Join(tempDir, "split")
	rawZipPath, err := optionalSingleField(upload.fields, "zip_path")
	if err != nil {
		writeUploadError(c, err)
		return
	}
	directOutput := rawZipPath != ""
	zipPath := ""
	if directOutput {
		if c.GetHeader(directSplitExportHeader) != "1" || !hasLoopbackOrigin(c.GetHeader("Origin")) {
			writeError(c, http.StatusForbidden, "L’export direct est réservé à l’application de bureau.")
			return
		}
		zipPath = filepath.Clean(rawZipPath)
		if strings.ContainsRune(zipPath, 0) || !filepath.IsAbs(zipPath) || !strings.EqualFold(filepath.Ext(zipPath), ".zip") {
			writeError(c, http.StatusBadRequest, "Le chemin du ZIP sélectionné est invalide.")
			return
		}
		outputDir = filepath.Dir(zipPath)
		info, err := os.Stat(outputDir)
		if err != nil {
			log.Printf("pdf-toolkit: inspect split output directory: %v", err)
			writeError(c, http.StatusBadRequest, "Le dossier de destination est inaccessible.")
			return
		}
		if !info.IsDir() {
			writeError(c, http.StatusBadRequest, "Le dossier de destination est invalide.")
			return
		}
		if info, err := os.Lstat(zipPath); err == nil && info.IsDir() {
			writeError(c, http.StatusBadRequest, "Le chemin du ZIP désigne un dossier.")
			return
		} else if err != nil && !errors.Is(err, os.ErrNotExist) {
			log.Printf("pdf-toolkit: inspect split archive destination: %v", err)
			writeError(c, http.StatusInternalServerError, "Impossible de vérifier le fichier ZIP de destination.")
			return
		}
	} else {
		if c.GetHeader(directSplitExportHeader) == "1" {
			writeError(c, http.StatusBadRequest, "Le chemin du ZIP de destination est requis.")
			return
		}
		if err := os.Mkdir(outputDir, 0o700); err != nil {
			log.Printf("pdf-toolkit: create split directory: %v", err)
			writeError(c, http.StatusInternalServerError, "Impossible de créer l'espace temporaire de traitement.")
			return
		}
	}
	onProgress := func(completed, total int) {
		h.splitProgress.update(progressID, "extracting", completed, total)
	}
	var outputs []services.SplitOutput
	if directOutput {
		outputs, err = h.service.SplitToDirectoryWithProgress(c.Request.Context(), upload.files[0].path, outputDir, groups, onProgress)
	} else {
		outputs, err = h.service.SplitWithProgress(c.Request.Context(), upload.files[0].path, outputDir, groups, onProgress)
	}
	if err != nil {
		h.writeServiceError(c, err)
		return
	}
	if directOutput {
		defer func() {
			if cleanupErr := removeSplitOutputs(outputs); cleanupErr != nil {
				log.Printf("pdf-toolkit: clean direct split outputs: %v", cleanupErr)
			}
		}()
	}

	archivePath := filepath.Join(tempDir, "split.zip")
	if directOutput {
		archivePath = zipPath
	}
	h.splitProgress.update(progressID, "archiving", 0, len(outputs))
	if err := writeSplitArchive(archivePath, folder, outputs, func(completed, total int) {
		h.splitProgress.update(progressID, "archiving", completed, total)
	}); err != nil {
		log.Printf("pdf-toolkit: write split archive: %v", err)
		writeError(c, http.StatusInternalServerError, "Impossible de lire le PDF traité.")
		return
	}
	if directOutput {
		if err := removeSplitOutputs(outputs); err != nil {
			log.Printf("pdf-toolkit: remove direct split outputs after archive creation: %v", err)
			writeError(c, http.StatusInternalServerError, "Le ZIP a été créé, mais des PDF intermédiaires n'ont pas pu être supprimés.")
			return
		}
		outputs = nil
		c.Header("Cache-Control", "no-store")
		c.JSON(http.StatusOK, gin.H{"file_name": filepath.Base(zipPath)})
		return
	}
	sendFile(c, archivePath, folder+".zip", "application/zip")
}

func hasLoopbackOrigin(rawOrigin string) bool {
	origin, err := url.Parse(rawOrigin)
	if err != nil || origin.User != nil || origin.Path != "" || origin.RawQuery != "" || origin.Fragment != "" {
		return false
	}
	if origin.Scheme != "http" && origin.Scheme != "https" {
		return false
	}
	host := strings.ToLower(origin.Hostname())
	if host == "localhost" {
		return true
	}
	ip := net.ParseIP(host)
	return ip != nil && ip.IsLoopback()
}

func removeSplitOutputs(outputs []services.SplitOutput) error {
	var cleanupErr error
	for _, output := range outputs {
		if err := os.Remove(output.Path); err != nil && !errors.Is(err, os.ErrNotExist) {
			cleanupErr = errors.Join(cleanupErr, fmt.Errorf("remove split output %q: %w", output.Path, err))
		}
	}
	return cleanupErr
}

func writeSplitArchive(
	archivePath, folder string,
	outputs []services.SplitOutput,
	onProgress func(completed, total int),
) (err error) {
	file, err := os.CreateTemp(filepath.Dir(archivePath), ".pdf-toolkit-split-*.tmp")
	if err != nil {
		return fmt.Errorf("create archive: %w", err)
	}
	stagingPath := file.Name()
	fileClosed := false
	committed := false
	defer func() {
		if !fileClosed {
			if closeErr := file.Close(); closeErr != nil {
				err = errors.Join(err, fmt.Errorf("close archive: %w", closeErr))
			}
		}
		if !committed {
			if removeErr := os.Remove(stagingPath); removeErr != nil && !errors.Is(removeErr, os.ErrNotExist) {
				err = errors.Join(err, fmt.Errorf("remove incomplete archive: %w", removeErr))
			}
		}
	}()

	archive := zip.NewWriter(file)
	for index, output := range outputs {
		if err := addArchiveFile(archive, folder+"/"+output.Name, output.Path); err != nil {
			return errors.Join(err, archive.Close())
		}
		if onProgress != nil {
			onProgress(index+1, len(outputs))
		}
	}
	if err := archive.Close(); err != nil {
		return fmt.Errorf("finalize archive: %w", err)
	}
	if err := file.Sync(); err != nil {
		return fmt.Errorf("sync archive: %w", err)
	}
	if err := file.Close(); err != nil {
		return fmt.Errorf("close archive: %w", err)
	}
	fileClosed = true
	if err := os.Rename(stagingPath, archivePath); err != nil {
		return fmt.Errorf("publish archive: %w", err)
	}
	committed = true
	return nil
}

func addArchiveFile(archive *zip.Writer, name, sourcePath string) error {
	source, err := os.Open(sourcePath)
	if err != nil {
		return fmt.Errorf("open split document: %w", err)
	}
	defer source.Close()

	entry, err := archive.CreateHeader(&zip.FileHeader{Name: name, Method: zip.Deflate})
	if err != nil {
		return fmt.Errorf("add archive entry: %w", err)
	}
	if _, err := io.Copy(entry, source); err != nil {
		return fmt.Errorf("write archive entry: %w", err)
	}
	return nil
}

func sendFile(c *gin.Context, filePath, downloadName, contentType string) {
	file, err := os.Open(filePath)
	if err != nil {
		log.Printf("pdf-toolkit: open processed file: %v", err)
		writeError(c, http.StatusInternalServerError, "Impossible de lire le PDF traité.")
		return
	}
	defer file.Close()

	info, err := file.Stat()
	if err != nil {
		log.Printf("pdf-toolkit: inspect processed file: %v", err)
		writeError(c, http.StatusInternalServerError, "Impossible de lire le PDF traité.")
		return
	}

	disposition := mime.FormatMediaType("attachment", map[string]string{"filename": downloadName})
	if disposition == "" || strings.ContainsAny(downloadName, "\r\n") {
		disposition = "attachment; filename=" + defaultSplitFolder + ".zip"
	}
	c.Header("Content-Disposition", disposition)
	c.Header("Cache-Control", "no-store")
	c.Header("X-Content-Type-Options", "nosniff")
	c.DataFromReader(http.StatusOK, info.Size(), contentType, file, nil)
}
