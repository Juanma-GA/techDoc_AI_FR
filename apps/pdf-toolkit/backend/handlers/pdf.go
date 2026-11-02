package handlers

import (
	"context"
	"encoding/json"
	"errors"
	"log"
	"mime"
	"net/http"
	"os"
	"path/filepath"
	"strconv"

	"github.com/gin-gonic/gin"

	"pdf-toolkit/services"
)

type PDFHandler struct {
	service       *services.PDFService
	splitProgress *splitProgressStore
}

type errorResponse struct {
	Error string `json:"error"`
}

func NewPDFHandler(service *services.PDFService) *PDFHandler {
	return &PDFHandler{service: service, splitProgress: newSplitProgressStore()}
}

func (h *PDFHandler) RegisterRoutes(router gin.IRoutes) {
	router.GET("/health", h.Health)
	router.POST("/merge", h.Merge)
	router.POST("/images-to-pdf", h.ImagesToPDF)
	router.POST("/compress", h.Compress)
	router.POST("/extract", h.Extract)
	router.POST("/delete", h.Delete)
	router.POST("/insert", h.Insert)
	router.POST("/reorder", h.Reorder)
	router.POST("/rotate", h.Rotate)
	router.POST("/split", h.Split)
	router.GET("/split/progress/:jobID", h.SplitProgress)
	router.POST("/signature", h.Signature)
}

func (h *PDFHandler) Health(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"status": "ok"})
}

func (h *PDFHandler) Merge(c *gin.Context) {
	tempDir, ok := createWorkspace(c)
	if !ok {
		return
	}
	defer removeWorkspace(tempDir)

	upload, err := parseMultipart(c.Request, tempDir, "files", 0)
	if err != nil {
		writeUploadError(c, err)
		return
	}
	if len(upload.files) < 2 {
		writeError(c, http.StatusBadRequest, "Sélectionnez au moins deux fichiers PDF.")
		return
	}

	inputs := make([]string, len(upload.files))
	for index, file := range upload.files {
		inputs[index] = file.path
	}
	output := filepath.Join(tempDir, "merged.pdf")
	if err := h.service.Merge(c.Request.Context(), inputs, output); err != nil {
		h.writeServiceError(c, err)
		return
	}
	h.sendPDF(c, output, "merged.pdf")
}

func (h *PDFHandler) ImagesToPDF(c *gin.Context) {
	tempDir, ok := createWorkspace(c)
	if !ok {
		return
	}
	defer removeWorkspace(tempDir)

	upload, err := parseImageMultipart(c.Request, tempDir, "images", 0)
	if err != nil {
		writeUploadError(c, err)
		return
	}
	if len(upload.files) == 0 {
		writeError(c, http.StatusBadRequest, "Sélectionnez au moins une image PNG ou JPEG.")
		return
	}

	inputs := make([]string, len(upload.files))
	for index, file := range upload.files {
		inputs[index] = file.path
	}
	output := filepath.Join(tempDir, "images.pdf")
	if err := h.service.ImagesToPDF(c.Request.Context(), inputs, output); err != nil {
		h.writeServiceError(c, err)
		return
	}
	h.sendPDF(c, output, "images.pdf")
}

func (h *PDFHandler) Compress(c *gin.Context) {
	tempDir, ok := createWorkspace(c)
	if !ok {
		return
	}
	defer removeWorkspace(tempDir)

	upload, err := parseMultipart(c.Request, tempDir, "file", 1)
	if err != nil {
		writeUploadError(c, err)
		return
	}
	if len(upload.files) != 1 {
		writeError(c, http.StatusBadRequest, "Sélectionnez un fichier PDF.")
		return
	}

	output := filepath.Join(tempDir, "compressed.pdf")
	if err := h.service.Compress(c.Request.Context(), upload.files[0].path, output); err != nil {
		h.writeServiceError(c, err)
		return
	}
	h.sendPDF(c, output, "compressed.pdf")
}

func (h *PDFHandler) Extract(c *gin.Context) {
	tempDir, file, selection, ok := h.readSinglePDFForm(c, "pages")
	if !ok {
		return
	}
	defer removeWorkspace(tempDir)

	output := filepath.Join(tempDir, "extract.pdf")
	if err := h.service.Extract(c.Request.Context(), file.path, output, selection); err != nil {
		h.writeServiceError(c, err)
		return
	}
	h.sendPDF(c, output, "extract.pdf")
}

func (h *PDFHandler) Delete(c *gin.Context) {
	tempDir, file, selection, ok := h.readSinglePDFForm(c, "pages")
	if !ok {
		return
	}
	defer removeWorkspace(tempDir)

	output := filepath.Join(tempDir, "trimmed.pdf")
	if err := h.service.Delete(c.Request.Context(), file.path, output, selection); err != nil {
		h.writeServiceError(c, err)
		return
	}
	h.sendPDF(c, output, "trimmed.pdf")
}

func (h *PDFHandler) Insert(c *gin.Context) {
	tempDir, ok := createWorkspace(c)
	if !ok {
		return
	}
	defer removeWorkspace(tempDir)

	// files[0] is the target document (B), files[1] the source of the inserted pages (A).
	upload, err := parseMultipart(c.Request, tempDir, "files", 0, "pages", "after")
	if err != nil {
		writeUploadError(c, err)
		return
	}
	if len(upload.files) != 2 {
		writeError(c, http.StatusBadRequest, "Sélectionnez le PDF de destination puis le PDF source.")
		return
	}
	selection, err := optionalSingleField(upload.fields, "pages")
	if err != nil {
		writeUploadError(c, err)
		return
	}
	rawAfter, err := singleField(upload.fields, "after")
	if err != nil {
		writeUploadError(c, err)
		return
	}
	after, err := strconv.Atoi(rawAfter)
	if err != nil {
		writeError(c, http.StatusBadRequest, "La position d'insertion est invalide.")
		return
	}

	output := filepath.Join(tempDir, "inserted.pdf")
	if err := h.service.InsertPages(
		c.Request.Context(), upload.files[0].path, upload.files[1].path, output, selection, after,
	); err != nil {
		h.writeServiceError(c, err)
		return
	}
	h.sendPDF(c, output, "inserted.pdf")
}

func (h *PDFHandler) Reorder(c *gin.Context) {
	tempDir, ok := createWorkspace(c)
	if !ok {
		return
	}
	defer removeWorkspace(tempDir)

	upload, err := parseMultipart(c.Request, tempDir, "file", 1, "order")
	if err != nil {
		writeUploadError(c, err)
		return
	}
	if len(upload.files) != 1 {
		writeError(c, http.StatusBadRequest, "Sélectionnez un fichier PDF.")
		return
	}
	rawOrder, err := singleField(upload.fields, "order")
	if err != nil {
		writeUploadError(c, err)
		return
	}
	var order []int
	if err := json.Unmarshal([]byte(rawOrder), &order); err != nil || order == nil {
		writeError(c, http.StatusBadRequest, "L'ordre des pages est invalide.")
		return
	}

	output := filepath.Join(tempDir, "reordered.pdf")
	if err := h.service.Reorder(c.Request.Context(), upload.files[0].path, output, order); err != nil {
		h.writeServiceError(c, err)
		return
	}
	h.sendPDF(c, output, "reordered.pdf")
}

func (h *PDFHandler) Rotate(c *gin.Context) {
	tempDir, ok := createWorkspace(c)
	if !ok {
		return
	}
	defer removeWorkspace(tempDir)

	upload, err := parseMultipart(c.Request, tempDir, "file", 1, "pages", "rotation")
	if err != nil {
		writeUploadError(c, err)
		return
	}
	if len(upload.files) != 1 {
		writeError(c, http.StatusBadRequest, "Sélectionnez un fichier PDF.")
		return
	}
	selection, err := optionalSingleField(upload.fields, "pages")
	if err != nil {
		writeUploadError(c, err)
		return
	}
	rawRotation, err := singleField(upload.fields, "rotation")
	if err != nil {
		writeUploadError(c, err)
		return
	}
	rotation, err := strconv.Atoi(rawRotation)
	if err != nil {
		writeError(c, http.StatusBadRequest, "L'angle de rotation est invalide.")
		return
	}

	output := filepath.Join(tempDir, "rotated.pdf")
	if err := h.service.Rotate(c.Request.Context(), upload.files[0].path, output, selection, rotation); err != nil {
		h.writeServiceError(c, err)
		return
	}
	h.sendPDF(c, output, "rotated.pdf")
}

func (h *PDFHandler) readSinglePDFForm(c *gin.Context, textField string) (string, uploadedPDF, string, bool) {
	tempDir, ok := createWorkspace(c)
	if !ok {
		return "", uploadedPDF{}, "", false
	}

	upload, err := parseMultipart(c.Request, tempDir, "file", 1, textField)
	if err != nil {
		removeWorkspace(tempDir)
		writeUploadError(c, err)
		return "", uploadedPDF{}, "", false
	}
	if len(upload.files) != 1 {
		removeWorkspace(tempDir)
		writeError(c, http.StatusBadRequest, "Sélectionnez un fichier PDF.")
		return "", uploadedPDF{}, "", false
	}
	selection, err := singleField(upload.fields, textField)
	if err != nil {
		removeWorkspace(tempDir)
		writeUploadError(c, err)
		return "", uploadedPDF{}, "", false
	}
	return tempDir, upload.files[0], selection, true
}

func createWorkspace(c *gin.Context) (string, bool) {
	tempDir, err := os.MkdirTemp("", "pdf-toolkit-")
	if err != nil {
		log.Printf("pdf-toolkit: create temporary workspace: %v", err)
		writeError(c, http.StatusInternalServerError, "Impossible de créer l'espace temporaire de traitement.")
		return "", false
	}
	return tempDir, true
}

func removeWorkspace(tempDir string) {
	if err := os.RemoveAll(tempDir); err != nil {
		log.Printf("pdf-toolkit: remove temporary workspace %q: %v", tempDir, err)
	}
}

func (h *PDFHandler) sendPDF(c *gin.Context, filePath, downloadName string) {
	file, err := os.Open(filePath)
	if err != nil {
		log.Printf("pdf-toolkit: open processed PDF: %v", err)
		writeError(c, http.StatusInternalServerError, "Impossible de lire le PDF traité.")
		return
	}
	defer file.Close()

	info, err := file.Stat()
	if err != nil {
		log.Printf("pdf-toolkit: inspect processed PDF: %v", err)
		writeError(c, http.StatusInternalServerError, "Impossible de lire le PDF traité.")
		return
	}

	c.Header("Content-Disposition", mime.FormatMediaType("attachment", map[string]string{"filename": downloadName}))
	c.Header("Cache-Control", "no-store")
	c.Header("X-Content-Type-Options", "nosniff")
	c.DataFromReader(http.StatusOK, info.Size(), "application/pdf", file, nil)
}

func (h *PDFHandler) writeServiceError(c *gin.Context, err error) {
	if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
		return
	}
	if errors.Is(err, services.ErrUnsupportedSignatureText) {
		writeError(c, http.StatusBadRequest, "Le nom ou la date contient un caractère que le PDF ne peut pas afficher.")
		return
	}
	if errors.Is(err, services.ErrInvalidInput) {
		writeError(c, http.StatusBadRequest, "Vérifiez les options et le PDF sélectionnés.")
		return
	}
	if errors.Is(err, services.ErrOutputWrite) {
		log.Printf("pdf-toolkit: write PDF output: %v", err)
		writeError(c, http.StatusInternalServerError, "Impossible d’écrire les fichiers de sortie dans le dossier choisi.")
		return
	}
	if errors.Is(err, services.ErrInvalidPDF) {
		writeError(c, http.StatusUnprocessableEntity, "Le fichier fourni est invalide ou ne peut pas être traité.")
		return
	}
	log.Printf("pdf-toolkit: process PDF: %v", err)
	writeError(c, http.StatusInternalServerError, "Le traitement du PDF a échoué.")
}

func writeUploadError(c *gin.Context, err error) {
	var uploadErr *requestError
	if errors.As(err, &uploadErr) {
		writeError(c, uploadErr.status, uploadErr.message)
		return
	}
	log.Printf("pdf-toolkit: receive upload: %v", err)
	writeError(c, http.StatusInternalServerError, "Impossible de préparer les fichiers PDF.")
}

func writeError(c *gin.Context, status int, message string) {
	c.JSON(status, errorResponse{Error: message})
}
