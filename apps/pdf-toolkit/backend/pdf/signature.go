package pdf

import (
	"context"
	"fmt"
	"image"
	_ "image/jpeg"
	_ "image/png"
	"math"
	"os"
	"strconv"

	"github.com/pdfcpu/pdfcpu/pkg/api"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu/model"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu/types"
)

const maxSignaturePixels int64 = 16_000_000

func (p *PDFCPU) StampImage(
	ctx context.Context,
	input, imagePath, output string,
	page int,
	x, y, width float64,
) error {
	if err := ctx.Err(); err != nil {
		return err
	}

	pageDims, err := api.PageDimsFile(input)
	if err != nil {
		return fmt.Errorf("pdfcpu signature page dimensions: %w", err)
	}
	if page < 1 || page > len(pageDims) {
		return fmt.Errorf("signature page %d is outside the document", page)
	}

	imageFile, err := os.Open(imagePath)
	if err != nil {
		return fmt.Errorf("open signature image: %w", err)
	}
	imageConfig, _, decodeErr := image.DecodeConfig(imageFile)
	closeErr := imageFile.Close()
	if decodeErr != nil {
		return fmt.Errorf("decode signature image dimensions: %w", decodeErr)
	}
	if closeErr != nil {
		return fmt.Errorf("close signature image: %w", closeErr)
	}
	if imageConfig.Width < 1 || imageConfig.Height < 1 ||
		int64(imageConfig.Width)*int64(imageConfig.Height) > maxSignaturePixels {
		return fmt.Errorf("signature image dimensions exceed the supported limit")
	}

	pageDim := pageDims[page-1]
	if pageDim.Width <= 0 || pageDim.Height <= 0 {
		return fmt.Errorf("PDF page dimensions are invalid")
	}
	description, height, err := signatureStampDescription(pageDim, imageConfig, x, y, width)
	if err != nil {
		return err
	}
	if math.IsInf(height, 0) || math.IsNaN(height) || y+height > 1 {
		return fmt.Errorf("signature image does not fit on the selected page")
	}

	if err := api.AddImageWatermarksFile(
		input,
		output,
		[]string{strconv.Itoa(page)},
		true,
		imagePath,
		description,
		model.NewDefaultConfiguration(),
	); err != nil {
		return fmt.Errorf("pdfcpu signature stamp: %w", err)
	}
	return ctx.Err()
}

func signatureStampDescription(
	pageDim types.Dim,
	imageConfig image.Config,
	x, y, width float64,
) (string, float64, error) {
	if pageDim.Width <= 0 || pageDim.Height <= 0 ||
		imageConfig.Width <= 0 || imageConfig.Height <= 0 {
		return "", 0, fmt.Errorf("signature or PDF dimensions are invalid")
	}
	imageAspectRatio := float64(imageConfig.Width) / float64(imageConfig.Height)
	imageWidth := width * pageDim.Width
	imageHeight := imageWidth / imageAspectRatio
	height := imageHeight / pageDim.Height
	if imageWidth <= 0 || math.IsInf(height, 0) || math.IsNaN(height) {
		return "", 0, fmt.Errorf("signature placement is invalid")
	}

	offsetX := x * pageDim.Width
	offsetY := (1 - y - height) * pageDim.Height
	scale := imageWidth / float64(imageConfig.Width)
	description := fmt.Sprintf(
		"position:bl, offset:%f %f, scalefactor:%f abs, rotation:0",
		offsetX,
		offsetY,
		scale,
	)
	return description, height, nil
}
