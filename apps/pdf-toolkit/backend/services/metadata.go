package services

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"unicode/utf8"
)

type PDFMetadata struct {
	Title    string
	Author   string
	Subject  string
	Keywords string
}

func (s *PDFService) EditMetadata(ctx context.Context, input, output string, metadata PDFMetadata) error {
	if input == "" || output == "" || input == output {
		return fmt.Errorf("%w: distinct input and output paths are required", ErrInvalidInput)
	}
	for _, value := range []string{metadata.Title, metadata.Author, metadata.Subject, metadata.Keywords} {
		if !utf8.ValidString(value) || strings.ContainsRune(value, '\x00') {
			return fmt.Errorf("%w: metadata must be valid text without null characters", ErrInvalidInput)
		}
	}
	if err := ctx.Err(); err != nil {
		return err
	}
	if err := s.processor.EditMetadata(ctx, input, output, metadata); err != nil {
		if errors.Is(err, context.Canceled) ||
			errors.Is(err, context.DeadlineExceeded) ||
			errors.Is(err, ErrOutputWrite) {
			return err
		}
		return fmt.Errorf("%w: edit PDF metadata: %w", ErrInvalidPDF, err)
	}
	return nil
}
