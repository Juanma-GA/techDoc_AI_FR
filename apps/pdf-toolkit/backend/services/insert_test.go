package services

import (
	"context"
	"errors"
	"reflect"
	"testing"
)

func TestInsertPagesBuildsTargetOrder(t *testing.T) {
	tests := []struct {
		name      string
		selection string
		after     int
		want      []int
	}{
		// Target B has 4 pages (1-4); source A pages become 5-7 in the merged document.
		{name: "at start", selection: "", after: 0, want: []int{5, 6, 7, 1, 2, 3, 4}},
		{name: "in the middle keeps typed order", selection: "3,1", after: 2, want: []int{1, 2, 7, 5, 3, 4}},
		{name: "at end", selection: "2", after: 4, want: []int{1, 2, 3, 4, 6}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			processor := &fakeProcessor{pageCounts: map[string]int{"b.pdf": 4, "a.pdf": 3}}
			service := NewPDFService(processor)
			if err := service.InsertPages(context.Background(), "b.pdf", "a.pdf", "out.pdf", test.selection, test.after); err != nil {
				t.Fatalf("InsertPages() error = %v", err)
			}
			if !reflect.DeepEqual(processor.merged, []string{"b.pdf", "a.pdf"}) {
				t.Fatalf("merged inputs = %v, want target then source", processor.merged)
			}
			if !reflect.DeepEqual(processor.collected, test.want) {
				t.Fatalf("collected = %v, want %v", processor.collected, test.want)
			}
		})
	}
}

func TestInsertPagesRejectsInvalidInput(t *testing.T) {
	tests := []struct {
		name      string
		selection string
		after     int
	}{
		{name: "negative position", after: -1},
		{name: "position after last page", after: 5},
		{name: "source page outside document", selection: "4", after: 1},
		{name: "duplicate source page", selection: "1,1", after: 1},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			processor := &fakeProcessor{pageCounts: map[string]int{"b.pdf": 4, "a.pdf": 3}}
			err := NewPDFService(processor).InsertPages(context.Background(), "b.pdf", "a.pdf", "out.pdf", test.selection, test.after)
			if !errors.Is(err, ErrInvalidInput) {
				t.Fatalf("InsertPages() error = %v, want ErrInvalidInput", err)
			}
			if processor.merged != nil {
				t.Fatalf("documents were merged despite invalid input")
			}
		})
	}
}

func TestInsertPagesWrapsProcessorFailures(t *testing.T) {
	processor := &fakeProcessor{pageCount: 2, collectErr: errors.New("broken")}
	err := NewPDFService(processor).InsertPages(context.Background(), "b.pdf", "a.pdf", "out.pdf", "", 1)
	if !errors.Is(err, ErrInvalidPDF) {
		t.Fatalf("InsertPages() error = %v, want ErrInvalidPDF", err)
	}
}
