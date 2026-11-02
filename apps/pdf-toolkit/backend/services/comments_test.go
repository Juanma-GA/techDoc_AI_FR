package services

import (
	"context"
	"errors"
	"strings"
	"testing"
)

func TestAddCommentsValidatesAndDelegates(t *testing.T) {
	comments := []PDFComment{
		{Page: 2, X1: 123.5, Y1: 456.25, X2: 140, Y2: 470, Content: "À vérifier"},
	}
	processor := &fakeProcessor{pageCount: 3}
	service := NewPDFService(processor)

	if err := service.AddComments(context.Background(), "input.pdf", "output.pdf", comments); err != nil {
		t.Fatalf("AddComments() error = %v", err)
	}
	if len(processor.comments) != 1 || processor.comments[0] != comments[0] {
		t.Fatalf("AddComments() delegated comments = %+v, want %+v", processor.comments, comments)
	}
}

func TestAddCommentsRejectsInvalidInput(t *testing.T) {
	tooManyComments := make([]PDFComment, maxPDFComments+1)
	for index := range tooManyComments {
		tooManyComments[index] = PDFComment{
			Page: 1, X1: 1, Y1: 1, X2: 2, Y2: 2, Content: "Note",
		}
	}
	validComment := PDFComment{
		Page: 1, X1: 10, Y1: 10, X2: 20, Y2: 20, Content: "Note",
	}
	invalidPosition := validComment
	invalidPosition.X1 = 1e9
	zeroWidth := validComment
	zeroWidth.X2 = zeroWidth.X1
	zeroHeight := validComment
	zeroHeight.Y2 = zeroHeight.Y1
	tooLong := validComment
	tooLong.Content = strings.Repeat("a", maxPDFCommentRunes+1)
	tests := []struct {
		name     string
		input    string
		output   string
		comments []PDFComment
	}{
		{name: "missing input", input: "", output: "output.pdf", comments: []PDFComment{validComment}},
		{name: "missing output", input: "input.pdf", output: "", comments: []PDFComment{validComment}},
		{name: "no comments", input: "input.pdf", output: "output.pdf"},
		{name: "too many comments", input: "input.pdf", output: "output.pdf", comments: tooManyComments},
		{name: "page zero", input: "input.pdf", output: "output.pdf", comments: []PDFComment{{Page: 0, X1: 10, Y1: 10, X2: 20, Y2: 20, Content: "Note"}}},
		{name: "empty content", input: "input.pdf", output: "output.pdf", comments: []PDFComment{{Page: 1, X1: 10, Y1: 10, X2: 20, Y2: 20, Content: "  "}}},
		{name: "invalid position", input: "input.pdf", output: "output.pdf", comments: []PDFComment{invalidPosition}},
		{name: "zero width", input: "input.pdf", output: "output.pdf", comments: []PDFComment{zeroWidth}},
		{name: "zero height", input: "input.pdf", output: "output.pdf", comments: []PDFComment{zeroHeight}},
		{name: "too long", input: "input.pdf", output: "output.pdf", comments: []PDFComment{tooLong}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			err := NewPDFService(&fakeProcessor{pageCount: 3}).AddComments(
				context.Background(),
				test.input,
				test.output,
				test.comments,
			)
			if !errors.Is(err, ErrInvalidInput) {
				t.Fatalf("AddComments() error = %v, want ErrInvalidInput", err)
			}
		})
	}
}

func TestAddCommentsRejectsPagesOutsideDocument(t *testing.T) {
	err := NewPDFService(&fakeProcessor{pageCount: 2}).AddComments(
		context.Background(),
		"input.pdf",
		"output.pdf",
		[]PDFComment{{Page: 3, X1: 10, Y1: 10, X2: 20, Y2: 20, Content: "Note"}},
	)
	if !errors.Is(err, ErrInvalidInput) {
		t.Fatalf("AddComments() error = %v, want ErrInvalidInput", err)
	}
}
