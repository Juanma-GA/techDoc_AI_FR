package pdf

import (
	"context"
	"fmt"
	"image"
	"os"
	"path/filepath"
	"strconv"
	"testing"

	"github.com/pdfcpu/pdfcpu/pkg/api"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu/model"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu/types"

	"pdf-toolkit/services"
)

func TestStampSignatureAffectsOnlySelectedPage(t *testing.T) {
	tempDir := t.TempDir()
	input := filepath.Join(tempDir, "input.pdf")
	signature := filepath.Join(tempDir, "signature.png")
	output := filepath.Join(tempDir, "signed.pdf")
	if err := os.WriteFile(input, testPDF(t, 3), 0o600); err != nil {
		t.Fatal(err)
	}
	writeTestPNG(t, signature)

	processor := NewPDFCPU()
	options := services.SignatureStampOptions{
		Page:          2,
		ImagePosition: services.StampPosition{X: 0.2, Y: 0.6},
		ImageWidth:    0.3,
		Name: &services.SignatureTextStamp{
			Text:     "Élodie D'Aubigné",
			Position: services.StampPosition{X: 0.1, Y: 0.86},
		},
		Date: &services.SignatureTextStamp{
			Text:     "22/10/2026",
			Position: services.StampPosition{X: 0.1, Y: 0.92},
		},
	}
	if err := processor.StampSignature(context.Background(), input, signature, output, options); err != nil {
		t.Fatalf("StampSignature() error = %v", err)
	}
	assertPageCount(t, processor, output, 3)

	for page := 1; page <= 3; page++ {
		t.Run(fmt.Sprintf("page_%d", page), func(t *testing.T) {
			pageFile := filepath.Join(tempDir, fmt.Sprintf("page-%d.pdf", page))
			if err := api.TrimFile(output, pageFile, []string{strconv.Itoa(page)}, model.NewDefaultConfiguration()); err != nil {
				t.Fatalf("TrimFile() error = %v", err)
			}
			file, err := os.Open(pageFile)
			if err != nil {
				t.Fatalf("open extracted page: %v", err)
			}
			images, extractErr := api.ExtractImagesRaw(file, []string{"1"}, model.NewDefaultConfiguration())
			closeErr := file.Close()
			if extractErr != nil {
				t.Fatalf("ExtractImagesRaw() error = %v", extractErr)
			}
			if closeErr != nil {
				t.Fatalf("close extracted page: %v", closeErr)
			}
			hasImage := len(images) == 1 && len(images[0]) > 0
			if want := page == 2; hasImage != want {
				t.Fatalf("page contains an image = %t, want %t", hasImage, want)
			}
		})
	}
}

func TestStampSignatureRejectsPlacementOutsidePage(t *testing.T) {
	tempDir := t.TempDir()
	input := filepath.Join(tempDir, "input.pdf")
	signature := filepath.Join(tempDir, "signature.png")
	output := filepath.Join(tempDir, "signed.pdf")
	if err := os.WriteFile(input, testPDF(t, 1), 0o600); err != nil {
		t.Fatal(err)
	}
	writeTestPNG(t, signature)

	err := NewPDFCPU().StampSignature(context.Background(), input, signature, output, services.SignatureStampOptions{
		Page:          1,
		ImagePosition: services.StampPosition{X: 0.2, Y: 0.9},
		ImageWidth:    0.3,
	})
	if err == nil {
		t.Fatal("StampSignature() error = nil, want placement error")
	}
	if _, statErr := os.Stat(output); !os.IsNotExist(statErr) {
		t.Fatalf("output PDF exists after rejected placement: %v", statErr)
	}
}

func TestStampSignatureSupportsRotatedPage(t *testing.T) {
	tempDir := t.TempDir()
	input := filepath.Join(tempDir, "input.pdf")
	rotated := filepath.Join(tempDir, "rotated.pdf")
	signature := filepath.Join(tempDir, "signature.png")
	output := filepath.Join(tempDir, "signed.pdf")
	if err := os.WriteFile(input, testPDF(t, 1), 0o600); err != nil {
		t.Fatal(err)
	}
	writeTestPNG(t, signature)
	if err := api.RotateFile(input, rotated, 90, nil, model.NewDefaultConfiguration()); err != nil {
		t.Fatalf("RotateFile() error = %v", err)
	}

	if err := NewPDFCPU().StampSignature(context.Background(), rotated, signature, output, services.SignatureStampOptions{
		Page:          1,
		ImagePosition: services.StampPosition{X: 0.2, Y: 0.6},
		ImageWidth:    0.3,
	}); err != nil {
		t.Fatalf("StampSignature() on rotated page error = %v", err)
	}
	assertPageCount(t, NewPDFCPU(), output, 1)

	file, err := os.Open(output)
	if err != nil {
		t.Fatal(err)
	}
	images, extractErr := api.ExtractImagesRaw(file, []string{"1"}, model.NewDefaultConfiguration())
	closeErr := file.Close()
	if extractErr != nil {
		t.Fatalf("ExtractImagesRaw() error = %v", extractErr)
	}
	if closeErr != nil {
		t.Fatalf("close signed PDF: %v", closeErr)
	}
	if len(images) != 1 || len(images[0]) == 0 {
		t.Fatal("signature image was not embedded on the rotated page")
	}
}

func TestSignatureStampDescriptionDisablesDefaultDiagonal(t *testing.T) {
	signature := filepath.Join(t.TempDir(), "signature.png")
	writeTestPNG(t, signature)

	description, _, err := signatureStampDescription(
		types.Dim{Width: 792, Height: 612},
		image.Config{Width: 240, Height: 80},
		0.15,
		0.65,
		0.3,
	)
	if err != nil {
		t.Fatalf("signatureStampDescription() error = %v", err)
	}

	watermark, err := api.ImageWatermark(signature, description, true, false, types.POINTS)
	if err != nil {
		t.Fatalf("ImageWatermark() error = %v", err)
	}
	if watermark.Rotation != 0 || watermark.Diagonal != model.NoDiagonal {
		t.Fatalf("watermark rotation = %v, diagonal = %d, want upright image", watermark.Rotation, watermark.Diagonal)
	}
}

func TestSignatureTextStampDescriptionKeepsFourteenPointSize(t *testing.T) {
	description := signatureTextStampDescription(
		types.Dim{Width: 792, Height: 612},
		services.StampPosition{X: 0.12, Y: 0.86},
	)
	watermark, err := api.TextWatermark("Élodie D'Aubigné", description, true, false, types.POINTS)
	if err != nil {
		t.Fatalf("TextWatermark() error = %v", err)
	}
	if watermark.FontSize != 14 || watermark.Scale != 1 || !watermark.ScaleAbs ||
		watermark.Rotation != 0 || watermark.Diagonal != model.NoDiagonal {
		t.Fatalf("unexpected text watermark config: points=%d scale=%v absolute=%t rotation=%v diagonal=%d",
			watermark.FontSize,
			watermark.Scale,
			watermark.ScaleAbs,
			watermark.Rotation,
			watermark.Diagonal,
		)
	}
}
