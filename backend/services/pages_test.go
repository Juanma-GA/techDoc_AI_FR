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
	pageCount int
	deleted   []int
	reordered []int
}

func (p *fakeProcessor) Merge(context.Context, []string, string) error { return nil }
func (p *fakeProcessor) PageCount(context.Context, string) (int, error) {
	return p.pageCount, nil
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
