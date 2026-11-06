package handlers

import (
	"net/http"
	"path/filepath"

	"github.com/gin-gonic/gin"

	"pdf-toolkit/services"
)

func (h *PDFHandler) EditMetadata(c *gin.Context) {
	tempDir, ok := createWorkspace(c)
	if !ok {
		return
	}
	defer removeWorkspace(tempDir)

	upload, err := parseMultipart(c.Request, tempDir, "file", 1, "title", "author", "subject", "keywords")
	if err != nil {
		writeUploadError(c, err)
		return
	}
	if len(upload.files) != 1 {
		writeError(c, http.StatusBadRequest, "Sélectionnez un fichier PDF.")
		return
	}

	values := make(map[string]string, 4)
	for _, name := range []string{"title", "author", "subject", "keywords"} {
		value, err := optionalSingleField(upload.fields, name)
		if err != nil || len(upload.fields[name]) != 1 {
			writeError(c, http.StatusBadRequest, "Vérifiez les options et le PDF sélectionnés.")
			return
		}
		values[name] = value
	}
	metadata := services.PDFMetadata{
		Title: values["title"], Author: values["author"],
		Subject: values["subject"], Keywords: values["keywords"],
	}
	output := filepath.Join(tempDir, "metadata.pdf")
	if err := h.service.EditMetadata(c.Request.Context(), upload.files[0].path, output, metadata); err != nil {
		h.writeServiceError(c, err)
		return
	}
	h.sendPDF(c, output, "metadata.pdf")
}
