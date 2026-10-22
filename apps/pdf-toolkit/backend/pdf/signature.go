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
	"strings"

	"github.com/pdfcpu/pdfcpu/pkg/api"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu/model"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu/types"

	"pdf-toolkit/services"
)

const maxSignaturePixels int64 = 16_000_000

func (p *PDFCPU) StampSignature(
	ctx context.Context,
	input, imagePath, output string,
	options services.SignatureStampOptions,
) error {
	if err := ctx.Err(); err != nil {
		return err
	}

	pageDims, err := api.PageDimsFile(input)
	if err != nil {
		return fmt.Errorf("pdfcpu signature page dimensions: %w", err)
	}
	if options.Page < 1 || options.Page > len(pageDims) {
		return fmt.Errorf("signature page %d is outside the document", options.Page)
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

	pageDim := pageDims[options.Page-1]
	if pageDim.Width <= 0 || pageDim.Height <= 0 {
		return fmt.Errorf("PDF page dimensions are invalid")
	}
	description, height, err := signatureStampDescription(
		pageDim,
		imageConfig,
		options.ImagePosition.X,
		options.ImagePosition.Y,
		options.ImageWidth,
	)
	if err != nil {
		return err
	}
	if math.IsInf(height, 0) || math.IsNaN(height) || options.ImagePosition.Y+height > 1 {
		return fmt.Errorf("signature image does not fit on the selected page")
	}

	if err := api.AddImageWatermarksFile(
		input,
		output,
		[]string{strconv.Itoa(options.Page)},
		true,
		imagePath,
		description,
		model.NewDefaultConfiguration(),
	); err != nil {
		return fmt.Errorf("pdfcpu signature stamp: %w", err)
	}

	for _, textStamp := range []*services.SignatureTextStamp{options.Name, options.Date} {
		if textStamp == nil {
			continue
		}
		if err := ctx.Err(); err != nil {
			return err
		}
		if err := p.stampText(ctx, output, options.Page, *textStamp); err != nil {
			return fmt.Errorf("pdfcpu signature text stamp: %w", err)
		}
	}
	return ctx.Err()
}

func (p *PDFCPU) stampText(
	ctx context.Context,
	input string,
	page int,
	stamp services.SignatureTextStamp,
) error {
	pageDims, err := api.PageDimsFile(input)
	if err != nil {
		return fmt.Errorf("read page dimensions: %w", err)
	}
	if page < 1 || page > len(pageDims) {
		return fmt.Errorf("signature text page %d is outside the document", page)
	}
	pageDim := pageDims[page-1]
	if pageDim.Width <= 0 || pageDim.Height <= 0 {
		return fmt.Errorf("PDF page dimensions are invalid")
	}

	description := signatureTextStampDescription(pageDim, stamp.Position)
	if err := api.AddTextWatermarksFile(
		input,
		input,
		[]string{strconv.Itoa(page)},
		true,
		strings.TrimSpace(stamp.Text),
		description,
		model.NewDefaultConfiguration(),
	); err != nil {
		return fmt.Errorf("add signature text: %w", err)
	}
	return ctx.Err()
}

func signatureTextStampDescription(pageDim types.Dim, position services.StampPosition) string {
	return fmt.Sprintf(
		"fontname:Helvetica, points:14, color:0 0 0, position:tl, offset:%f %f, rotation:0, scalefactor:1 abs, maxwidth:%f",
		position.X*pageDim.Width,
		-position.Y*pageDim.Height,
		pageDim.Width*0.8,
	)
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
