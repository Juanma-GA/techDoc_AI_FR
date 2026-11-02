package services

import (
	"context"
	"errors"
	"reflect"
	"testing"
)

func TestParsePageSelection(t *testing.T) {
	tests := []struct {
		name      string
		selection string
		pageCount int
		want      []int
		wantErr   bool
	}{
		{name: "single page", selection: "1", pageCount: 8, want: []int{1}},
		{name: "range and list", selection: "2-4, 8", pageCount: 8, want: []int{2, 3, 4, 8}},
		{name: "preserves requested selection", selection: "5,1", pageCount: 8, want: []int{5, 1}},
		{name: "empty selection", selection: " ", pageCount: 8, wantErr: true},
		{name: "page zero", selection: "0", pageCount: 8, wantErr: true},
		{name: "outside document", selection: "1-9", pageCount: 8, wantErr: true},
		{name: "descending range", selection: "5-2", pageCount: 8, wantErr: true},
		{name: "duplicate page", selection: "1-3,3", pageCount: 8, wantErr: true},
		{name: "malformed range", selection: "1--3", pageCount: 8, wantErr: true},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, err := ParsePageSelection(test.selection, test.pageCount)
			if (err != nil) != test.wantErr {
				t.Fatalf("ParsePageSelection() error = %v, wantErr %t", err, test.wantErr)
			}
			if !test.wantErr && !reflect.DeepEqual(got, test.want) {
				t.Fatalf("ParsePageSelection() = %v, want %v", got, test.want)
			}
		})
	}
}

type fakeProcessor struct {
	pageCount    int
	pageCounts   map[string]int
	merged       []string
	collected    []int
	collectErr   error
	deleted      []int
	reordered    []int
	rotated      []int
	rotation     int
	compressCall bool
}

func (p *fakeProcessor) Merge(_ context.Context, inputs []string, _ string) error {
	p.merged = append([]string(nil), inputs...)
	return nil
}
func (p *fakeProcessor) ImagesToPDF(context.Context, []string, string) error { return nil }
func (p *fakeProcessor) Compress(context.Context, string, string) error {
	p.compressCall = true
	return nil
}
func (p *fakeProcessor) Protect(context.Context, string, string, PDFProtectionOptions) error {
	return nil
}
func (p *fakeProcessor) ChangeUserPassword(
	context.Context,
	string,
	string,
	PDFPasswordChangeOptions,
) error {
	return nil
}
func (p *fakeProcessor) PageCount(_ context.Context, input string) (int, error) {
	if count, ok := p.pageCounts[input]; ok {
		return count, nil
	}
	return p.pageCount, nil
}
func (p *fakeProcessor) Collect(_ context.Context, _, _ string, pages []int) error {
	p.collected = append([]int(nil), pages...)
	return p.collectErr
}
func (p *fakeProcessor) Extract(context.Context, string, string, []int) error { return nil }
func (p *fakeProcessor) Delete(_ context.Context, _, _ string, pages []int) error {
	p.deleted = append([]int(nil), pages...)
	return nil
}
func (p *fakeProcessor) Reorder(_ context.Context, _, _ string, pages []int) error {
	p.reordered = append([]int(nil), pages...)
	return nil
}
func (p *fakeProcessor) Rotate(_ context.Context, _, _ string, pages []int, rotation int) error {
	p.rotated = append([]int(nil), pages...)
	p.rotation = rotation
	return nil
}

func TestDeleteCannotRemoveEveryPage(t *testing.T) {
	service := NewPDFService(&fakeProcessor{pageCount: 3})
	err := service.Delete(context.Background(), "input.pdf", "output.pdf", "1-3")
	if !errors.Is(err, ErrInvalidInput) {
		t.Fatalf("Delete() error = %v, want ErrInvalidInput", err)
	}
}

func TestReorderRequiresEveryPageExactlyOnce(t *testing.T) {
	processor := &fakeProcessor{pageCount: 3}
	service := NewPDFService(processor)

	if err := service.Reorder(context.Background(), "input.pdf", "output.pdf", []int{3, 1, 2}); err != nil {
		t.Fatalf("Reorder() error = %v", err)
	}
	if !reflect.DeepEqual(processor.reordered, []int{3, 1, 2}) {
		t.Fatalf("Reorder() pages = %v, want [3 1 2]", processor.reordered)
	}

	err := service.Reorder(context.Background(), "input.pdf", "output.pdf", []int{1, 1, 3})
	if !errors.Is(err, ErrInvalidInput) {
		t.Fatalf("Reorder() error = %v, want ErrInvalidInput", err)
	}
}

func TestRotateUsesSelectedPagesAndRotatesAllWhenSelectionIsEmpty(t *testing.T) {
	processor := &fakeProcessor{pageCount: 4}
	service := NewPDFService(processor)

	if err := service.Rotate(context.Background(), "input.pdf", "output.pdf", "1,3-4", 270); err != nil {
		t.Fatalf("Rotate() error = %v", err)
	}
	if !reflect.DeepEqual(processor.rotated, []int{1, 3, 4}) {
		t.Fatalf("Rotate() pages = %v, want [1 3 4]", processor.rotated)
	}
	if processor.rotation != 270 {
		t.Fatalf("Rotate() rotation = %d, want 270", processor.rotation)
	}

	if err := service.Rotate(context.Background(), "input.pdf", "output.pdf", " ", 90); err != nil {
		t.Fatalf("Rotate() with empty selection error = %v", err)
	}
	if len(processor.rotated) != 0 {
		t.Fatalf("Rotate() with empty selection pages = %v, want all pages", processor.rotated)
	}
}

func TestRotateRejectsInvalidRotationAndPageSelection(t *testing.T) {
	service := NewPDFService(&fakeProcessor{pageCount: 4})

	if err := service.Rotate(context.Background(), "input.pdf", "output.pdf", "", 45); !errors.Is(err, ErrInvalidInput) {
		t.Fatalf("Rotate() with invalid angle error = %v, want ErrInvalidInput", err)
	}
	if err := service.Rotate(context.Background(), "input.pdf", "output.pdf", "4-2", 90); !errors.Is(err, ErrInvalidInput) {
		t.Fatalf("Rotate() with invalid pages error = %v, want ErrInvalidInput", err)
	}
}
