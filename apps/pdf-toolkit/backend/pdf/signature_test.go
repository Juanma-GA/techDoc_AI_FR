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
)

func TestStampImageAffectsOnlySelectedPage(t *testing.T) {
	tempDir := t.TempDir()
	input := filepath.Join(tempDir, "input.pdf")
	signature := filepath.Join(tempDir, "signature.png")
	output := filepath.Join(tempDir, "signed.pdf")
	if err := os.WriteFile(input, testPDF(t, 3), 0o600); err != nil {
		t.Fatal(err)
	}
	writeTestPNG(t, signature)

	processor := NewPDFCPU()
	if err := processor.StampImage(context.Background(), input, signature, output, 2, 0.2, 0.6, 0.3); err != nil {
		t.Fatalf("StampImage() error = %v", err)
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

func TestStampImageRejectsPlacementOutsidePage(t *testing.T) {
	tempDir := t.TempDir()
	input := filepath.Join(tempDir, "input.pdf")
	signature := filepath.Join(tempDir, "signature.png")
	output := filepath.Join(tempDir, "signed.pdf")
	if err := os.WriteFile(input, testPDF(t, 1), 0o600); err != nil {
		t.Fatal(err)
	}
	writeTestPNG(t, signature)

	err := NewPDFCPU().StampImage(context.Background(), input, signature, output, 1, 0.2, 0.9, 0.3)
	if err == nil {
		t.Fatal("StampImage() error = nil, want placement error")
	}
	if _, statErr := os.Stat(output); !os.IsNotExist(statErr) {
		t.Fatalf("output PDF exists after rejected placement: %v", statErr)
	}
}

func TestStampImageSupportsRotatedPage(t *testing.T) {
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

	if err := NewPDFCPU().StampImage(context.Background(), rotated, signature, output, 1, 0.2, 0.6, 0.3); err != nil {
		t.Fatalf("StampImage() on rotated page error = %v", err)
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
