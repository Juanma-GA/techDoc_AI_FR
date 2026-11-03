package handlers

import (
	"net/http"
	"path/filepath"

	"github.com/gin-gonic/gin"
)

func (h *PDFHandler) Clean(c *gin.Context) {
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

	output := filepath.Join(tempDir, "cleaned.pdf")
	if err := h.service.Clean(c.Request.Context(), upload.files[0].path, output); err != nil {
		h.writeServiceError(c, err)
		return
	}
	h.sendPDF(c, output, "cleaned.pdf")
}
