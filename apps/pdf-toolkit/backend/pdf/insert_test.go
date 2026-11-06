package pdf

import (
	"context"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/pdfcpu/pdfcpu/pkg/api"

	"pdf-toolkit/services"
)

func TestInsertPagesWithPDFCPUPreservesRequestedOrder(t *testing.T) {
	tempDir := t.TempDir()
	target := filepath.Join(tempDir, "target.pdf")
	source := filepath.Join(tempDir, "source.pdf")
	if err := os.WriteFile(target, testPDFWithWidths(t, 101, 102, 103), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(source, testPDFWithWidths(t, 201, 202, 203), 0o600); err != nil {
		t.Fatal(err)
	}

	service := services.NewPDFService(NewPDFCPU())
	tests := []struct {
		name      string
		selection string
		after     int
		want      []int
	}{
		{name: "start", selection: "", after: 0, want: []int{201, 202, 203, 101, 102, 103}},
		{name: "middle typed order", selection: "3,1", after: 2, want: []int{101, 102, 203, 201, 103}},
		{name: "end", selection: "2", after: 3, want: []int{101, 102, 103, 202}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			output := filepath.Join(tempDir, test.name+".pdf")
			if err := service.InsertPages(context.Background(), target, source, output, test.selection, test.after); err != nil {
				t.Fatalf("InsertPages() error = %v", err)
			}
			dims, err := api.PageDimsFile(output)
			if err != nil {
				t.Fatalf("PageDimsFile() error = %v", err)
			}
			widths := make([]int, len(dims))
			for index, dim := range dims {
				widths[index] = int(dim.Width)
			}
			if !reflect.DeepEqual(widths, test.want) {
				t.Fatalf("page widths = %v, want %v", widths, test.want)
			}
			if _, err := os.Stat(output + ".merged.pdf"); !os.IsNotExist(err) {
				t.Fatalf("intermediate merged file was not removed: %v", err)
			}
		})
	}
}
