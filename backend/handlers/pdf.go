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

	"github.com/gin-gonic/gin"

	"pdf-toolkit/services"
)

type PDFHandler struct {
	service *services.PDFService
}

type errorResponse struct {
	Error string `json:"error"`
}

func NewPDFHandler(service *services.PDFService) *PDFHandler {
	return &PDFHandler{service: service}
}

func (h *PDFHandler) RegisterRoutes(router gin.IRoutes) {
	router.GET("/health", h.Health)
	router.POST("/merge", h.Merge)
	router.POST("/extract", h.Extract)
	router.POST("/delete", h.Delete)
	router.POST("/reorder", h.Reorder)
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
	if errors.Is(err, services.ErrInvalidInput) {
		writeError(c, http.StatusBadRequest, "Vérifiez les pages et les fichiers sélectionnés.")
		return
	}
	if errors.Is(err, services.ErrInvalidPDF) {
		writeError(c, http.StatusUnprocessableEntity, "Le PDF est invalide, chiffré ou ne peut pas être traité.")
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
