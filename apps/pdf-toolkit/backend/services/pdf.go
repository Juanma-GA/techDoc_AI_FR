package services

import (
	"context"
	"errors"
	"fmt"
	"strings"
)

var (
	ErrInvalidInput = errors.New("invalid PDF operation input")
	ErrInvalidPDF   = errors.New("invalid or unsupported PDF")
	ErrOutputWrite  = errors.New("PDF output could not be written")
)

type PDFProcessor interface {
	Merge(ctx context.Context, inputFiles []string, output string) error
	ImagesToPDF(ctx context.Context, inputFiles []string, output string) error
	Compress(ctx context.Context, input, output string) error
	PageCount(ctx context.Context, input string) (int, error)
	Extract(ctx context.Context, input, output string, pages []int) error
	Delete(ctx context.Context, input, output string, pages []int) error
	Reorder(ctx context.Context, input, output string, pages []int) error
	Rotate(ctx context.Context, input, output string, pages []int, rotation int) error
	StampSignature(ctx context.Context, input, image, output string, options SignatureStampOptions) error
}

type SplitDocument interface {
	PageCount() int
	Extract(ctx context.Context, output string, pages []int) error
	Close() error
}

type SplitDocumentProvider interface {
	OpenSplitDocument(ctx context.Context, input string) (SplitDocument, error)
}

type PDFService struct {
	processor PDFProcessor
}

func NewPDFService(processor PDFProcessor) *PDFService {
	return &PDFService{processor: processor}
}

func (s *PDFService) Merge(ctx context.Context, inputFiles []string, output string) error {
	if len(inputFiles) < 2 || output == "" {
		return fmt.Errorf("%w: at least two PDFs are required", ErrInvalidInput)
	}
	if err := ctx.Err(); err != nil {
		return err
	}
	if err := s.processor.Merge(ctx, inputFiles, output); err != nil {
		if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
			return err
		}
		return fmt.Errorf("%w: merge: %w", ErrInvalidPDF, err)
	}
	return nil
}

func (s *PDFService) Compress(ctx context.Context, input, output string) error {
	if input == "" || output == "" {
		return fmt.Errorf("%w: input and output paths are required", ErrInvalidInput)
	}
	if err := ctx.Err(); err != nil {
		return err
	}
	if err := s.processor.Compress(ctx, input, output); err != nil {
		if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
			return err
		}
		return fmt.Errorf("%w: compress PDF: %w", ErrInvalidPDF, err)
	}
	return nil
}

func (s *PDFService) ImagesToPDF(ctx context.Context, inputFiles []string, output string) error {
	if len(inputFiles) == 0 || output == "" {
		return fmt.Errorf("%w: images and output path are required", ErrInvalidInput)
	}
	for _, input := range inputFiles {
		if input == "" {
			return fmt.Errorf("%w: image paths must not be empty", ErrInvalidInput)
		}
	}
	if err := ctx.Err(); err != nil {
		return err
	}
	if err := s.processor.ImagesToPDF(ctx, inputFiles, output); err != nil {
		if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
			return err
		}
		return fmt.Errorf("%w: convert images to PDF: %w", ErrInvalidPDF, err)
	}
	return nil
}

func (s *PDFService) Extract(ctx context.Context, input, output, selection string) error {
	pages, _, err := s.selectedPages(ctx, input, selection)
	if err != nil {
		return err
	}
	if output == "" {
		return fmt.Errorf("%w: output path is required", ErrInvalidInput)
	}
	if err := s.processor.Extract(ctx, input, output, pages); err != nil {
		if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
			return err
		}
		return fmt.Errorf("%w: extract pages: %w", ErrInvalidPDF, err)
	}
	return nil
}

func (s *PDFService) Delete(ctx context.Context, input, output, selection string) error {
	pages, pageCount, err := s.selectedPages(ctx, input, selection)
	if err != nil {
		return err
	}
	if len(pages) == pageCount {
		return fmt.Errorf("%w: a PDF must keep at least one page", ErrInvalidInput)
	}
	if output == "" {
		return fmt.Errorf("%w: output path is required", ErrInvalidInput)
	}
	if err := s.processor.Delete(ctx, input, output, pages); err != nil {
		if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
			return err
		}
		return fmt.Errorf("%w: delete pages: %w", ErrInvalidPDF, err)
	}
	return nil
}

func (s *PDFService) Reorder(ctx context.Context, input, output string, order []int) error {
	pageCount, err := s.pageCount(ctx, input)
	if err != nil {
		return err
	}
	if output == "" || !isPagePermutation(order, pageCount) {
		return fmt.Errorf("%w: order must contain every page exactly once", ErrInvalidInput)
	}
	if err := s.processor.Reorder(ctx, input, output, order); err != nil {
		if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
			return err
		}
		return fmt.Errorf("%w: reorder pages: %w", ErrInvalidPDF, err)
	}
	return nil
}

func (s *PDFService) Rotate(ctx context.Context, input, output, selection string, rotation int) error {
	if output == "" || !isSupportedRotation(rotation) {
		return fmt.Errorf("%w: output path or rotation is invalid", ErrInvalidInput)
	}
	pageCount, err := s.pageCount(ctx, input)
	if err != nil {
		return err
	}

	var pages []int
	if strings.TrimSpace(selection) != "" {
		pages, err = ParsePageSelection(selection, pageCount)
		if err != nil {
			return err
		}
	}

	if err := s.processor.Rotate(ctx, input, output, pages, rotation); err != nil {
		if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
			return err
		}
		return fmt.Errorf("%w: rotate pages: %w", ErrInvalidPDF, err)
	}
	return nil
}

func (s *PDFService) selectedPages(ctx context.Context, input, selection string) ([]int, int, error) {
	if input == "" {
		return nil, 0, fmt.Errorf("%w: input PDF is required", ErrInvalidInput)
	}
	pageCount, err := s.pageCount(ctx, input)
	if err != nil {
		return nil, 0, err
	}
	pages, err := ParsePageSelection(selection, pageCount)
	return pages, pageCount, err
}

func (s *PDFService) pageCount(ctx context.Context, input string) (int, error) {
	if input == "" {
		return 0, fmt.Errorf("%w: input PDF is required", ErrInvalidInput)
	}
	if err := ctx.Err(); err != nil {
		return 0, err
	}
	pageCount, err := s.processor.PageCount(ctx, input)
	if err != nil {
		if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
			return 0, err
		}
		return 0, fmt.Errorf("%w: read page count: %w", ErrInvalidPDF, err)
	}
	if pageCount < 1 {
		return 0, fmt.Errorf("%w: PDF does not contain pages", ErrInvalidPDF)
	}
	return pageCount, nil
}

func isSupportedRotation(rotation int) bool {
	return rotation == 90 || rotation == 180 || rotation == 270
}

func isPagePermutation(order []int, pageCount int) bool {
	if len(order) != pageCount {
		return false
	}
	seen := make([]bool, pageCount+1)
	for _, page := range order {
		if page < 1 || page > pageCount || seen[page] {
			return false
		}
		seen[page] = true
	}
	return true
}
