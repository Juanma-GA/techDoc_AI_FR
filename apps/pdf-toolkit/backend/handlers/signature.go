package handlers

import (
	"fmt"
	"net/http"
	"path/filepath"
	"strconv"

	"github.com/gin-gonic/gin"

	"pdf-toolkit/services"
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

	nameText, nameErr := optionalSingleField(upload.fields, "name_text")
	dateText, dateErr := optionalSingleField(upload.fields, "date_text")
	if nameErr != nil || dateErr != nil {
		writeError(c, http.StatusBadRequest, "Vérifiez les options et le PDF sélectionnés.")
		return
	}

	options := services.SignatureStampOptions{
		Page:          pageNumber,
		ImagePosition: services.StampPosition{X: xPosition, Y: yPosition},
		ImageWidth:    signatureWidth,
	}
	if nameText != "" {
		position, err := parseSignatureTextPosition(upload.fields, "name")
		if err != nil {
			writeError(c, http.StatusBadRequest, "Vérifiez les options et le PDF sélectionnés.")
			return
		}
		options.Name = &services.SignatureTextStamp{Text: nameText, Position: position}
	}
	if dateText != "" {
		position, err := parseSignatureTextPosition(upload.fields, "date")
		if err != nil {
			writeError(c, http.StatusBadRequest, "Vérifiez les options et le PDF sélectionnés.")
			return
		}
		options.Date = &services.SignatureTextStamp{Text: dateText, Position: position}
	}

	output := filepath.Join(tempDir, "signed.pdf")
	if err := h.service.ApplySignature(
		c.Request.Context(),
		upload.pdfPath,
		upload.signaturePath,
		output,
		options,
	); err != nil {
		h.writeServiceError(c, err)
		return
	}
	h.sendPDF(c, output, "signed.pdf")
}

func parseSignatureTextPosition(fields map[string][]string, prefix string) (services.StampPosition, error) {
	rawX, err := singleField(fields, prefix+"_x")
	if err != nil {
		return services.StampPosition{}, err
	}
	rawY, err := singleField(fields, prefix+"_y")
	if err != nil {
		return services.StampPosition{}, err
	}
	x, xErr := strconv.ParseFloat(rawX, 64)
	y, yErr := strconv.ParseFloat(rawY, 64)
	if xErr != nil || yErr != nil {
		return services.StampPosition{}, fmt.Errorf("signature %s position is invalid", prefix)
	}
	return services.StampPosition{X: x, Y: y}, nil
}
