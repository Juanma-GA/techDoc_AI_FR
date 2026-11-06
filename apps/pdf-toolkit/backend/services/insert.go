package services

import (
	"context"
	"errors"
	"fmt"
	"os"
	"strings"
)

// InsertPages inserts the selected source pages, in the requested order, after page `after` of the target.
// An empty selection inserts every source page; after = 0 inserts before the first target page.
func (s *PDFService) InsertPages(ctx context.Context, target, source, output, selection string, after int) (err error) {
	if output == "" {
		return fmt.Errorf("%w: output path is required", ErrInvalidInput)
	}
	targetCount, err := s.pageCount(ctx, target)
	if err != nil {
		return err
	}
	sourceCount, err := s.pageCount(ctx, source)
	if err != nil {
		return err
	}
	if after < 0 || after > targetCount {
		return fmt.Errorf("%w: insertion position is outside the target document", ErrInvalidInput)
	}

	var pages []int
	if strings.TrimSpace(selection) == "" {
		pages = make([]int, sourceCount)
		for index := range pages {
			pages[index] = index + 1
		}
	} else if pages, err = ParsePageSelection(selection, sourceCount); err != nil {
		return err
	}

	order := make([]int, 0, targetCount+len(pages))
	for page := 1; page <= after; page++ {
		order = append(order, page)
	}
	for _, page := range pages {
		order = append(order, targetCount+page)
	}
	for page := after + 1; page <= targetCount; page++ {
		order = append(order, page)
	}

	merged := output + ".merged.pdf"
	defer func() {
		if removeErr := os.Remove(merged); removeErr != nil && !errors.Is(removeErr, os.ErrNotExist) {
			err = errors.Join(err, fmt.Errorf("remove intermediate insert file: %w", removeErr))
		}
	}()
	if err := s.processor.Merge(ctx, []string{target, source}, merged); err != nil {
		if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
			return err
		}
		return fmt.Errorf("%w: combine documents for insertion: %w", ErrInvalidPDF, err)
	}
	if err := s.processor.Collect(ctx, merged, output, order); err != nil {
		if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
			return err
		}
		return fmt.Errorf("%w: insert pages: %w", ErrInvalidPDF, err)
	}
	return nil
}
