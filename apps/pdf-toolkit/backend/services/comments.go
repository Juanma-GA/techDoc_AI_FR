package services

import (
	"context"
	"errors"
	"fmt"
	"math"
	"strings"
	"unicode/utf8"
)

const (
	maxPDFComments      = 100
	maxPDFCommentRunes  = 2000
	maxPDFCommentPoints = 100_000
)

type PDFComment struct {
	Page    int     `json:"page"`
	X       float64 `json:"x"`
	Y       float64 `json:"y"`
	Content string  `json:"content"`
}

func (s *PDFService) AddComments(
	ctx context.Context,
	input, output string,
	comments []PDFComment,
) error {
	if input == "" || output == "" || len(comments) == 0 || len(comments) > maxPDFComments {
		return fmt.Errorf("%w: comment input or count is invalid", ErrInvalidInput)
	}
	for _, comment := range comments {
		content := strings.TrimSpace(comment.Content)
		if comment.Page < 1 ||
			math.IsNaN(comment.X) || math.IsInf(comment.X, 0) ||
			math.IsNaN(comment.Y) || math.IsInf(comment.Y, 0) ||
			math.Abs(comment.X) > maxPDFCommentPoints ||
			math.Abs(comment.Y) > maxPDFCommentPoints ||
			content == "" || utf8.RuneCountInString(content) > maxPDFCommentRunes ||
			strings.ContainsRune(comment.Content, '\x00') {
			return fmt.Errorf("%w: comment placement or content is invalid", ErrInvalidInput)
		}
	}
	if err := ctx.Err(); err != nil {
		return err
	}
	pageCount, err := s.pageCount(ctx, input)
	if err != nil {
		return err
	}
	for _, comment := range comments {
		if comment.Page > pageCount {
			return fmt.Errorf("%w: comment page is outside the document", ErrInvalidInput)
		}
	}
	if err := ctx.Err(); err != nil {
		return err
	}
	if err := s.processor.AddComments(ctx, input, output, comments); err != nil {
		if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
			return err
		}
		return fmt.Errorf("%w: add PDF comments: %w", ErrInvalidPDF, err)
	}
	return nil
}
