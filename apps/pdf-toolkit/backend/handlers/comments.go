package handlers

import (
	"encoding/json"
	"net/http"
	"path/filepath"

	"github.com/gin-gonic/gin"

	"pdf-toolkit/services"
)

func (h *PDFHandler) Comments(c *gin.Context) {
	tempDir, ok := createWorkspace(c)
	if !ok {
		return
	}
	defer removeWorkspace(tempDir)

	upload, err := parseMultipart(c.Request, tempDir, "file", 1, "comments")
	if err != nil {
		writeUploadError(c, err)
		return
	}
	if len(upload.files) != 1 {
		writeError(c, http.StatusBadRequest, "Sélectionnez un fichier PDF.")
		return
	}
	rawComments, err := singleField(upload.fields, "comments")
	if err != nil {
		writeError(c, http.StatusBadRequest, "Vérifiez les commentaires et le PDF sélectionnés.")
		return
	}
	var comments []services.PDFComment
	if err := json.Unmarshal([]byte(rawComments), &comments); err != nil {
		writeError(c, http.StatusBadRequest, "Vérifiez les commentaires et le PDF sélectionnés.")
		return
	}

	output := filepath.Join(tempDir, "commented.pdf")
	if err := h.service.AddComments(
		c.Request.Context(),
		upload.files[0].path,
		output,
		comments,
	); err != nil {
		h.writeServiceError(c, err)
		return
	}
	h.sendPDF(c, output, "commented.pdf")
}
