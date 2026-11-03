package services

import (
	"context"
	"errors"
	"math"
	"reflect"
	"testing"
)

type cropTestProcessor struct {
	fakeProcessor
	crops   []PDFCropRect
	cropErr error
}

func (p *fakeProcessor) Crop(context.Context, string, string, []PDFCropRect) error {
	return nil
}

func (p *cropTestProcessor) Crop(_ context.Context, _, _ string, crops []PDFCropRect) error {
	p.crops = append([]PDFCropRect(nil), crops...)
	return p.cropErr
}

func TestCropValidatesAndDelegates(t *testing.T) {
	processor := &cropTestProcessor{fakeProcessor: fakeProcessor{pageCount: 2}}
	crops := []PDFCropRect{
		{Page: 2, X1: 10, Y1: 20, X2: 500, Y2: 700},
		{Page: 1, X1: 15, Y1: 25, X2: 510, Y2: 710},
	}

	if err := NewPDFService(processor).Crop(context.Background(), "input.pdf", "output.pdf", crops); err != nil {
		t.Fatalf("Crop() error = %v", err)
	}
	if !reflect.DeepEqual(processor.crops, crops) {
		t.Fatalf("Crop() rectangles = %+v, want %+v", processor.crops, crops)
	}
}

func TestCropRejectsInvalidRequest(t *testing.T) {
	valid := []PDFCropRect{{Page: 1, X1: 10, Y1: 10, X2: 100, Y2: 100}}
	tests := []struct {
		name      string
		input     string
		output    string
		pageCount int
		crops     []PDFCropRect
	}{
		{name: "missing input", input: "", output: "output.pdf", crops: valid},
		{name: "missing output", input: "input.pdf", output: "", crops: valid},
		{name: "missing rectangles", input: "input.pdf", output: "output.pdf"},
		{
			name:   "missing page",
			input:  "input.pdf",
			output: "output.pdf",
			crops:  []PDFCropRect{{Page: 2, X1: 10, Y1: 10, X2: 100, Y2: 100}},
		},
		{
			name:      "duplicate page",
			input:     "input.pdf",
			output:    "output.pdf",
			pageCount: 2,
			crops: []PDFCropRect{
				{Page: 1, X1: 10, Y1: 10, X2: 100, Y2: 100},
				{Page: 1, X1: 20, Y1: 20, X2: 110, Y2: 110},
			},
		},
		{
			name:   "non-finite coordinate",
			input:  "input.pdf",
			output: "output.pdf",
			crops:  []PDFCropRect{{Page: 1, X1: math.NaN(), Y1: 10, X2: 100, Y2: 100}},
		},
		{
			name:   "empty rectangle",
			input:  "input.pdf",
			output: "output.pdf",
			crops:  []PDFCropRect{{Page: 1, X1: 10, Y1: 10, X2: 10, Y2: 100}},
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			pageCount := test.pageCount
			if pageCount == 0 {
				pageCount = 1
			}
			processor := &cropTestProcessor{fakeProcessor: fakeProcessor{pageCount: pageCount}}
			err := NewPDFService(processor).Crop(
				context.Background(),
				test.input,
				test.output,
				test.crops,
			)
			if !errors.Is(err, ErrInvalidInput) {
				t.Fatalf("Crop() error = %v, want ErrInvalidInput", err)
			}
			if len(processor.crops) != 0 {
				t.Fatalf("Crop() called processor with invalid rectangles: %+v", processor.crops)
			}
		})
	}
}

func TestCropWrapsProcessorErrors(t *testing.T) {
	processor := &cropTestProcessor{
		fakeProcessor: fakeProcessor{pageCount: 1},
		cropErr:       errors.New("invalid crop PDF"),
	}
	err := NewPDFService(processor).Crop(
		context.Background(),
		"input.pdf",
		"output.pdf",
		[]PDFCropRect{{Page: 1, X1: 10, Y1: 10, X2: 100, Y2: 100}},
	)
	if !errors.Is(err, ErrInvalidPDF) {
		t.Fatalf("Crop() error = %v, want ErrInvalidPDF", err)
	}
}
