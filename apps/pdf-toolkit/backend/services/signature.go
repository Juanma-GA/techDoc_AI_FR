package services

import (
	"context"
	"errors"
	"fmt"
	"math"
	"strings"
	"unicode/utf8"
)

var ErrUnsupportedSignatureText = errors.New("unsupported signature text")

type StampPosition struct {
	X float64
	Y float64
}

type SignatureTextStamp struct {
	Text     string
	Position StampPosition
	FontSize int
}

type SignatureStampOptions struct {
	Page          int
	ImagePosition StampPosition
	ImageWidth    float64
	Name          *SignatureTextStamp
	Date          *SignatureTextStamp
}

func (s *PDFService) ApplySignature(
	ctx context.Context,
	input, image, output string,
	options SignatureStampOptions,
) error {
	if hasUnsupportedPdfText(options.Name) || hasUnsupportedPdfText(options.Date) {
		return ErrUnsupportedSignatureText
	}
	if input == "" || image == "" || output == "" || options.Page < 1 ||
		!isUnitCoordinate(options.ImagePosition.X) ||
		!isUnitCoordinate(options.ImagePosition.Y) ||
		!isUnitCoordinate(options.ImageWidth) ||
		options.ImageWidth == 0 ||
		options.ImagePosition.X+options.ImageWidth > 1 ||
		!isValidTextStamp(options.Name, 201) ||
		!isValidTextStamp(options.Date, 40) {
		return fmt.Errorf("%w: signature placement is invalid", ErrInvalidInput)
	}

	pageCount, err := s.pageCount(ctx, input)
	if err != nil {
		return err
	}
	if options.Page > pageCount {
		return fmt.Errorf("%w: signature page is outside the document", ErrInvalidInput)
	}
	if err := ctx.Err(); err != nil {
		return err
	}
	if err := s.processor.StampSignature(ctx, input, image, output, options); err != nil {
		if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
			return err
		}
		return fmt.Errorf("%w: apply signature image: %w", ErrInvalidPDF, err)
	}
	return nil
}

func isValidTextStamp(stamp *SignatureTextStamp, maxRunes int) bool {
	if stamp == nil {
		return true
	}
	text := strings.TrimSpace(stamp.Text)
	if text == "" || utf8.RuneCountInString(text) > maxRunes ||
		strings.ContainsAny(text, "\r\n\x00") ||
		stamp.FontSize < 6 || stamp.FontSize > 48 {
		return false
	}
	return isUnitCoordinate(stamp.Position.X) &&
		isUnitCoordinate(stamp.Position.Y) &&
		stamp.Position.Y <= 0.95
}

func hasUnsupportedPdfText(stamp *SignatureTextStamp) bool {
	if stamp == nil {
		return false
	}
	for _, character := range stamp.Text {
		if character > 0xFF {
			return true
		}
	}
	return false
}

func isUnitCoordinate(value float64) bool {
	return !math.IsNaN(value) && !math.IsInf(value, 0) && value >= 0 && value <= 1
}
