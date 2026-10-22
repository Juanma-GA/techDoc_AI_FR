package services

import (
	"context"
	"errors"
	"fmt"
	"math"
)

func (s *PDFService) ApplySignature(
	ctx context.Context,
	input, image, output string,
	page int,
	x, y, width float64,
) error {
	if input == "" || image == "" || output == "" || page < 1 ||
		!isUnitCoordinate(x) || !isUnitCoordinate(y) ||
		!isUnitCoordinate(width) || width == 0 || x+width > 1 {
		return fmt.Errorf("%w: signature placement is invalid", ErrInvalidInput)
	}

	pageCount, err := s.pageCount(ctx, input)
	if err != nil {
		return err
	}
	if page > pageCount {
		return fmt.Errorf("%w: signature page is outside the document", ErrInvalidInput)
	}
	if err := ctx.Err(); err != nil {
		return err
	}
	if err := s.processor.StampImage(ctx, input, image, output, page, x, y, width); err != nil {
		if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
			return err
		}
		return fmt.Errorf("%w: apply signature image: %w", ErrInvalidPDF, err)
	}
	return nil
}

func isUnitCoordinate(value float64) bool {
	return !math.IsNaN(value) && !math.IsInf(value, 0) && value >= 0 && value <= 1
}
