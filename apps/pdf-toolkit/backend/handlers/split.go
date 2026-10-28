package handlers

import (
	"archive/zip"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"mime"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"github.com/gin-gonic/gin"

	"pdf-toolkit/services"
)

const defaultSplitFolder = "split"

func (h *PDFHandler) Split(c *gin.Context) {
	tempDir, ok := createWorkspace(c)
	if !ok {
		return
	}
	defer removeWorkspace(tempDir)

	upload, err := parseMultipart(c.Request, tempDir, "file", 1, "groups", "folder")
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
	if err := os.Mkdir(outputDir, 0o700); err != nil {
		log.Printf("pdf-toolkit: create split directory: %v", err)
		writeError(c, http.StatusInternalServerError, "Impossible de créer l'espace temporaire de traitement.")
		return
	}
	outputs, err := h.service.Split(c.Request.Context(), upload.files[0].path, outputDir, groups)
	if err != nil {
		h.writeServiceError(c, err)
		return
	}

	archivePath := filepath.Join(tempDir, "split.zip")
	if err := writeSplitArchive(archivePath, folder, outputs); err != nil {
		log.Printf("pdf-toolkit: write split archive: %v", err)
		writeError(c, http.StatusInternalServerError, "Impossible de lire le PDF traité.")
		return
	}
	sendFile(c, archivePath, folder+".zip", "application/zip")
}

func writeSplitArchive(archivePath, folder string, outputs []services.SplitOutput) (err error) {
	file, err := os.OpenFile(archivePath, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return fmt.Errorf("create archive: %w", err)
	}
	defer func() {
		if closeErr := file.Close(); err == nil && closeErr != nil {
			err = fmt.Errorf("close archive: %w", closeErr)
		}
	}()

	archive := zip.NewWriter(file)
	for _, output := range outputs {
		if err := addArchiveFile(archive, folder+"/"+output.Name, output.Path); err != nil {
			_ = archive.Close()
			return err
		}
	}
	if err := archive.Close(); err != nil {
		return fmt.Errorf("finalize archive: %w", err)
	}
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
