package services

import (
	"context"
	"errors"
	"math"
	"testing"
)

func (p *fakeProcessor) StampImage(context.Context, string, string, string, int, float64, float64, float64) error {
	return nil
}

func TestApplySignatureValidatesPageAndPlacement(t *testing.T) {
	service := NewPDFService(&fakeProcessor{pageCount: 3})

	if err := service.ApplySignature(context.Background(), "input.pdf", "signature.png", "output.pdf", 2, 0.2, 0.6, 0.3); err != nil {
		t.Fatalf("ApplySignature() error = %v", err)
	}

	tests := []struct {
		name  string
		page  int
		x     float64
		y     float64
		width float64
	}{
		{name: "page outside PDF", page: 4, x: 0.2, y: 0.6, width: 0.3},
		{name: "placement outside page", page: 1, x: 0.8, y: 0.6, width: 0.3},
		{name: "non-finite coordinate", page: 1, x: math.NaN(), y: 0.6, width: 0.3},
		{name: "zero width", page: 1, x: 0.2, y: 0.6, width: 0},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			err := service.ApplySignature(
				context.Background(),
				"input.pdf",
				"signature.png",
				"output.pdf",
				test.page,
				test.x,
				test.y,
				test.width,
			)
			if err == nil || !errors.Is(err, ErrInvalidInput) {
				t.Fatalf("ApplySignature() error = %v, want ErrInvalidInput", err)
			}
		})
	}
}
