package services

import (
	"context"
	"errors"
	"math"
	"strings"
	"testing"
)

func (p *fakeProcessor) StampSignature(
	context.Context,
	string,
	string,
	string,
	SignatureStampOptions,
) error {
	return nil
}

func TestApplySignatureValidatesPageAndPlacement(t *testing.T) {
	service := NewPDFService(&fakeProcessor{pageCount: 3})
	options := SignatureStampOptions{
		Page:          2,
		ImagePosition: StampPosition{X: 0.2, Y: 0.6},
		ImageWidth:    0.3,
		Name: &SignatureTextStamp{
			Text:     "Ada Lovelace",
			Position: StampPosition{X: 0.1, Y: 0.86},
		},
		Date: &SignatureTextStamp{
			Text:     "22/10/2026",
			Position: StampPosition{X: 0.1, Y: 0.92},
		},
	}

	if err := service.ApplySignature(context.Background(), "input.pdf", "signature.png", "output.pdf", options); err != nil {
		t.Fatalf("ApplySignature() error = %v", err)
	}

	tests := []struct {
		name    string
		options SignatureStampOptions
	}{
		{
			name: "page outside PDF",
			options: SignatureStampOptions{
				Page:          4,
				ImagePosition: StampPosition{X: 0.2, Y: 0.6},
				ImageWidth:    0.3,
			},
		},
		{
			name: "placement outside page",
			options: SignatureStampOptions{
				Page:          1,
				ImagePosition: StampPosition{X: 0.8, Y: 0.6},
				ImageWidth:    0.3,
			},
		},
		{
			name: "non-finite coordinate",
			options: SignatureStampOptions{
				Page:          1,
				ImagePosition: StampPosition{X: math.NaN(), Y: 0.6},
				ImageWidth:    0.3,
			},
		},
		{
			name: "zero width",
			options: SignatureStampOptions{
				Page:          1,
				ImagePosition: StampPosition{X: 0.2, Y: 0.6},
			},
		},
		{
			name: "text position outside page",
			options: SignatureStampOptions{
				Page:          1,
				ImagePosition: StampPosition{X: 0.2, Y: 0.6},
				ImageWidth:    0.3,
				Name: &SignatureTextStamp{
					Text:     "Ada Lovelace",
					Position: StampPosition{X: 0.1, Y: 0.96},
				},
			},
		},
		{
			name: "text too long",
			options: SignatureStampOptions{
				Page:          1,
				ImagePosition: StampPosition{X: 0.2, Y: 0.6},
				ImageWidth:    0.3,
				Date: &SignatureTextStamp{
					Text:     strings.Repeat("x", 41),
					Position: StampPosition{X: 0.1, Y: 0.92},
				},
			},
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			err := service.ApplySignature(
				context.Background(),
				"input.pdf",
				"signature.png",
				"output.pdf",
				test.options,
			)
			if err == nil || !errors.Is(err, ErrInvalidInput) {
				t.Fatalf("ApplySignature() error = %v, want ErrInvalidInput", err)
			}
		})
	}
}

func TestApplySignatureRejectsTextUnsupportedByCorePDFFont(t *testing.T) {
	service := NewPDFService(&fakeProcessor{pageCount: 1})
	err := service.ApplySignature(
		context.Background(),
		"input.pdf",
		"signature.png",
		"output.pdf",
		SignatureStampOptions{
			Page:          1,
			ImagePosition: StampPosition{X: 0.2, Y: 0.6},
			ImageWidth:    0.3,
			Name: &SignatureTextStamp{
				Text:     "张伟",
				Position: StampPosition{X: 0.1, Y: 0.86},
			},
		},
	)
	if !errors.Is(err, ErrUnsupportedSignatureText) {
		t.Fatalf("ApplySignature() error = %v, want ErrUnsupportedSignatureText", err)
	}
}
