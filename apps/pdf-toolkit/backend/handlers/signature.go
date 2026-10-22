package handlers

import (
	"net/http"
	"path/filepath"
	"strconv"

	"github.com/gin-gonic/gin"
)

func (h *PDFHandler) Signature(c *gin.Context) {
	tempDir, ok := createWorkspace(c)
	if !ok {
		return
	}
	defer removeWorkspace(tempDir)

	upload, err := parseSignatureMultipart(c.Request, tempDir)
	if err != nil {
		writeUploadError(c, err)
		return
	}
	page, pageErr := singleField(upload.fields, "page")
	x, xErr := singleField(upload.fields, "x")
	y, yErr := singleField(upload.fields, "y")
	width, widthErr := singleField(upload.fields, "width")
	if pageErr != nil || xErr != nil || yErr != nil || widthErr != nil {
		writeError(c, http.StatusBadRequest, "Vérifiez les options et le PDF sélectionnés.")
		return
	}

	pageNumber, err := strconv.Atoi(page)
	if err != nil {
		writeError(c, http.StatusBadRequest, "Vérifiez les options et le PDF sélectionnés.")
		return
	}
	xPosition, xErr := strconv.ParseFloat(x, 64)
	yPosition, yErr := strconv.ParseFloat(y, 64)
	signatureWidth, widthErr := strconv.ParseFloat(width, 64)
	if xErr != nil || yErr != nil || widthErr != nil {
		writeError(c, http.StatusBadRequest, "Vérifiez les options et le PDF sélectionnés.")
		return
	}

	output := filepath.Join(tempDir, "signed.pdf")
	if err := h.service.ApplySignature(
		c.Request.Context(),
		upload.pdfPath,
		upload.signaturePath,
		output,
		pageNumber,
		xPosition,
		yPosition,
		signatureWidth,
	); err != nil {
		h.writeServiceError(c, err)
		return
	}
	h.sendPDF(c, output, "signed.pdf")
}
