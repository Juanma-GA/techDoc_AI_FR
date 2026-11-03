package pdf

import (
	"context"
	"errors"
	"math"
	"os"
	"path/filepath"
	"testing"

	"github.com/pdfcpu/pdfcpu/pkg/api"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu/model"

	"pdf-toolkit/services"
)

func TestPDFCPUCropSetsPageCropBoxes(t *testing.T) {
	tempDir := t.TempDir()
	input := filepath.Join(tempDir, "source.pdf")
	output := filepath.Join(tempDir, "cropped.pdf")
	if err := os.WriteFile(input, testPDF(t, 2), 0o600); err != nil {
		t.Fatal(err)
	}

	crops := []services.PDFCropRect{
		{Page: 1, X1: 12, Y1: 22, X2: 510, Y2: 700},
		{Page: 2, X1: 30, Y1: 40, X2: 590, Y2: 760},
	}
	if err := NewPDFCPU().Crop(context.Background(), input, output, crops); err != nil {
		t.Fatalf("Crop() error = %v", err)
	}

	file, err := os.Open(output)
	if err != nil {
		t.Fatalf("open cropped PDF: %v", err)
	}
	conf := model.NewDefaultConfiguration()
	conf.Cmd = model.CROP
	document, readErr := api.ReadValidateAndOptimize(file, conf)
	closeErr := file.Close()
	if err := errors.Join(readErr, closeErr); err != nil {
		t.Fatalf("read cropped PDF: %v", err)
	}

	for _, want := range crops {
		_, _, pageAttrs, err := document.PageDict(want.Page, false)
		if err != nil {
			t.Fatalf("read page %d boxes: %v", want.Page, err)
		}
		got := pageAttrs.CropBox
		if got == nil ||
			math.Abs(got.LL.X-want.X1) > 0.01 ||
			math.Abs(got.LL.Y-want.Y1) > 0.01 ||
			math.Abs(got.UR.X-want.X2) > 0.01 ||
			math.Abs(got.UR.Y-want.Y2) > 0.01 {
			t.Errorf("page %d crop box = %+v, want [%g %g %g %g]", want.Page, got, want.X1, want.Y1, want.X2, want.Y2)
		}
	}
}

func TestPDFCPUCropRejectsRectanglesOutsidePage(t *testing.T) {
	tempDir := t.TempDir()
	input := filepath.Join(tempDir, "source.pdf")
	output := filepath.Join(tempDir, "cropped.pdf")
	if err := os.WriteFile(input, testPDF(t, 1), 0o600); err != nil {
		t.Fatal(err)
	}

	err := NewPDFCPU().Crop(context.Background(), input, output, []services.PDFCropRect{
		{Page: 1, X1: 10, Y1: 10, X2: 700, Y2: 700},
	})
	if !errors.Is(err, services.ErrInvalidInput) {
		t.Fatalf("Crop() error = %v, want ErrInvalidInput", err)
	}
	if _, statErr := os.Stat(output); !errors.Is(statErr, os.ErrNotExist) {
		t.Fatalf("cropped PDF exists after invalid rectangle: %v", statErr)
	}
}
