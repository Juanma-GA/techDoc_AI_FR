package pdf

import (
	"context"
	"errors"
	"fmt"
	"math"
	"os"

	"github.com/pdfcpu/pdfcpu/pkg/api"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu/model"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu/types"

	"pdf-toolkit/services"
)

func (p *PDFCPU) Crop(ctx context.Context, input, output string, crops []services.PDFCropRect) error {
	if err := ctx.Err(); err != nil {
		return err
	}

	source, err := os.Open(input)
	if err != nil {
		return fmt.Errorf("pdfcpu crop open input: %w", err)
	}
	conf := model.NewDefaultConfiguration()
	conf.Cmd = model.CROP
	document, readErr := api.ReadValidateAndOptimize(source, conf)
	closeErr := source.Close()
	if operationErr := errors.Join(readErr, closeErr); operationErr != nil {
		return fmt.Errorf("pdfcpu crop read input: %w", operationErr)
	}
	if len(crops) != document.PageCount {
		return fmt.Errorf("%w: expected a crop rectangle for every page", services.ErrInvalidInput)
	}

	for _, crop := range crops {
		if err := ctx.Err(); err != nil {
			return err
		}
		if crop.Page < 1 || crop.Page > document.PageCount {
			return fmt.Errorf("%w: crop page is outside the document", services.ErrInvalidInput)
		}
		_, _, pageAttrs, err := document.PageDict(crop.Page, false)
		if err != nil {
			return fmt.Errorf("pdfcpu crop page %d: %w", crop.Page, err)
		}
		if pageAttrs == nil || pageAttrs.MediaBox == nil {
			return fmt.Errorf("pdfcpu crop page %d: missing media box", crop.Page)
		}
		rect, err := cropRectangle(crop, pageAttrs.MediaBox)
		if err != nil {
			return err
		}
		if err := document.Crop(types.IntSet{crop.Page: true}, &model.Box{Rect: rect}); err != nil {
			return fmt.Errorf("pdfcpu crop page %d: %w", crop.Page, err)
		}
	}

	if err := ctx.Err(); err != nil {
		return err
	}
	outputFile, err := os.OpenFile(output, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return fmt.Errorf("%w: create cropped PDF: %w", services.ErrOutputWrite, err)
	}
	writeErr := api.Write(document, outputFile, conf)
	outputCloseErr := outputFile.Close()
	if writeErr != nil || outputCloseErr != nil {
		outputErr := errors.Join(writeErr, outputCloseErr)
		removeErr := removeCropOutput(output)
		return errors.Join(
			fmt.Errorf("%w: write cropped PDF: %w", services.ErrOutputWrite, outputErr),
			removeErr,
		)
	}
	if err := ctx.Err(); err != nil {
		return errors.Join(err, removeCropOutput(output))
	}
	return nil
}

func cropRectangle(crop services.PDFCropRect, mediaBox *types.Rectangle) (*types.Rectangle, error) {
	const coordinateTolerance = 0.01

	clamp := func(value, min, max float64) (float64, bool) {
		if math.IsNaN(value) || math.IsInf(value, 0) || value < min-coordinateTolerance || value > max+coordinateTolerance {
			return value, false
		}
		return math.Min(math.Max(value, min), max), true
	}

	x1, validX1 := clamp(crop.X1, mediaBox.LL.X, mediaBox.UR.X)
	y1, validY1 := clamp(crop.Y1, mediaBox.LL.Y, mediaBox.UR.Y)
	x2, validX2 := clamp(crop.X2, mediaBox.LL.X, mediaBox.UR.X)
	y2, validY2 := clamp(crop.Y2, mediaBox.LL.Y, mediaBox.UR.Y)
	if !validX1 || !validY1 || !validX2 || !validY2 || x2 <= x1 || y2 <= y1 {
		return nil, fmt.Errorf("%w: crop rectangle is outside the page or has no area", services.ErrInvalidInput)
	}
	return types.NewRectangle(x1, y1, x2, y2), nil
}

func removeCropOutput(output string) error {
	if err := os.Remove(output); err != nil && !errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("remove incomplete cropped PDF: %w", err)
	}
	return nil
}
