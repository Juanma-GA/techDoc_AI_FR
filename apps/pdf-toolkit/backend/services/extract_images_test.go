package services

import (
	"context"
	"errors"
	"testing"
)

func TestExtractImagesValidatesAndDelegates(t *testing.T) {
	processor := &fakeProcessor{}
	service := NewPDFService(processor)

	if err := service.ExtractImages(context.Background(), "input.pdf", "images.zip"); err != nil {
		t.Fatalf("ExtractImages() error = %v", err)
	}
	if processor.imageInput != "input.pdf" || processor.imageOutput != "images.zip" {
		t.Fatalf("ExtractImages() paths = %q, %q", processor.imageInput, processor.imageOutput)
	}
}

func TestExtractImagesReportsInvalidInputAndNoImages(t *testing.T) {
	service := NewPDFService(&fakeProcessor{})
	if err := service.ExtractImages(context.Background(), "", "images.zip"); !errors.Is(err, ErrInvalidInput) {
		t.Fatalf("ExtractImages() with empty input error = %v, want ErrInvalidInput", err)
	}

	processor := &fakeProcessor{imageErr: ErrNoImages}
	err := NewPDFService(processor).ExtractImages(context.Background(), "input.pdf", "images.zip")
	if !errors.Is(err, ErrNoImages) || errors.Is(err, ErrInvalidPDF) {
		t.Fatalf("ExtractImages() with no images error = %v, want ErrNoImages", err)
	}
}

func TestExtractImagesWrapsProcessorErrorsAsInvalidPDF(t *testing.T) {
	err := NewPDFService(&fakeProcessor{imageErr: errors.New("corrupt image resource")}).
		ExtractImages(context.Background(), "input.pdf", "images.zip")
	if !errors.Is(err, ErrInvalidPDF) {
		t.Fatalf("ExtractImages() error = %v, want ErrInvalidPDF", err)
	}
}
