package handlers

import (
	"encoding/json"
	"net/http"
	"path/filepath"

	"github.com/gin-gonic/gin"

	"pdf-toolkit/services"
)

func (h *PDFHandler) Crop(c *gin.Context) {
	tempDir, upload, rawCrops, ok := h.readSinglePDFForm(c, "crops")
	if !ok {
		return
	}
	defer removeWorkspace(tempDir)

	var crops []services.PDFCropRect
	if err := json.Unmarshal([]byte(rawCrops), &crops); err != nil {
		writeError(c, http.StatusBadRequest, "Les zones de recadrage sont invalides.")
		return
	}

	output := filepath.Join(tempDir, "cropped.pdf")
	if err := h.service.Crop(c.Request.Context(), upload.path, output, crops); err != nil {
		h.writeServiceError(c, err)
		return
	}
	h.sendPDF(c, output, "cropped.pdf")
}
