package services

import (
	"context"
	"errors"
	"testing"
)

func TestEditMetadataValidatesAndDelegates(t *testing.T) {
	processor := &fakeProcessor{}
	service := NewPDFService(processor)
	metadata := PDFMetadata{Title: "Titre (revision)", Author: "Auteur", Keywords: "alpha, beta"}
	if err := service.EditMetadata(context.Background(), "input.pdf", "output.pdf", metadata); err != nil {
		t.Fatal(err)
	}
	if !processor.metadataCall || processor.metadata != metadata {
		t.Fatalf("metadata = %+v, want %+v", processor.metadata, metadata)
	}
	for _, test := range []struct {
		input, output string
		metadata      PDFMetadata
	}{
		{input: "", output: "output.pdf"},
		{input: "input.pdf", output: ""},
		{input: "input.pdf", output: "input.pdf"},
		{input: "input.pdf", output: "output.pdf", metadata: PDFMetadata{Title: "null\x00"}},
		{input: "input.pdf", output: "output.pdf", metadata: PDFMetadata{Author: "\xff"}},
	} {
		processor.metadataCall = false
		err := service.EditMetadata(context.Background(), test.input, test.output, test.metadata)
		if !errors.Is(err, ErrInvalidInput) || processor.metadataCall {
			t.Fatalf("invalid input: err = %v, called = %t", err, processor.metadataCall)
		}
	}
}

func TestEditMetadataPropagatesErrorsAndCancellation(t *testing.T) {
	for _, test := range []struct {
		err, want error
	}{
		{err: errors.New("broken PDF"), want: ErrInvalidPDF},
		{err: ErrOutputWrite, want: ErrOutputWrite},
		{err: context.Canceled, want: context.Canceled},
		{err: context.DeadlineExceeded, want: context.DeadlineExceeded},
	} {
		service := NewPDFService(&fakeProcessor{metadataErr: test.err})
		err := service.EditMetadata(context.Background(), "input.pdf", "output.pdf", PDFMetadata{})
		if !errors.Is(err, test.want) {
			t.Fatalf("err = %v, want %v", err, test.want)
		}
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	processor := &fakeProcessor{}
	err := NewPDFService(processor).EditMetadata(ctx, "input.pdf", "output.pdf", PDFMetadata{})
	if !errors.Is(err, context.Canceled) || processor.metadataCall {
		t.Fatalf("canceled request: err = %v, called = %t", err, processor.metadataCall)
	}
}
