package services

import (
	"context"
	"errors"
	"reflect"
	"strings"
	"testing"
)

type splitProcessor struct {
	fakeProcessor
	extracted [][]int
}

func (p *splitProcessor) Extract(_ context.Context, _, _ string, pages []int) error {
	p.extracted = append(p.extracted, append([]int(nil), pages...))
	return nil
}

func TestSplitExtractsEveryGroupWithUniqueNames(t *testing.T) {
	processor := &splitProcessor{fakeProcessor: fakeProcessor{pageCount: 6}}
	service := NewPDFService(processor)

	outputs, err := service.Split(context.Background(), "input.pdf", t.TempDir(), []SplitGroup{
		{Name: "DOC_A12_rev1", Pages: "1-2"},
		{Name: "doc_a12_rev1.pdf", Pages: "3,5"},
		{Name: "  ", Pages: "6"},
	})
	if err != nil {
		t.Fatalf("Split() error = %v", err)
	}
	if !reflect.DeepEqual(processor.extracted, [][]int{{1, 2}, {3, 5}, {6}}) {
		t.Fatalf("Split() pages = %v", processor.extracted)
	}
	names := []string{outputs[0].Name, outputs[1].Name, outputs[2].Name}
	want := []string{"DOC_A12_rev1.pdf", "doc_a12_rev1_2.pdf", "document-3.pdf"}
	if !reflect.DeepEqual(names, want) {
		t.Fatalf("Split() names = %v, want %v", names, want)
	}
}

func TestSplitAcceptsMaximumNumberOfGroups(t *testing.T) {
	processor := &splitProcessor{fakeProcessor: fakeProcessor{pageCount: 1}}
	service := NewPDFService(processor)
	groups := make([]SplitGroup, MaxSplitGroups)
	for index := range groups {
		groups[index] = SplitGroup{Name: "document", Pages: "1"}
	}

	outputs, err := service.Split(context.Background(), "input.pdf", t.TempDir(), groups)
	if err != nil {
		t.Fatalf("Split() error = %v", err)
	}
	if len(outputs) != MaxSplitGroups || len(processor.extracted) != MaxSplitGroups {
		t.Fatalf("Split() generated %d outputs and extracted %d groups, want %d", len(outputs), len(processor.extracted), MaxSplitGroups)
	}
}

func TestSplitRejectsInvalidGroups(t *testing.T) {
	service := NewPDFService(&splitProcessor{fakeProcessor: fakeProcessor{pageCount: 3}})
	tests := map[string][]SplitGroup{
		"no group":          nil,
		"page out of range": {{Name: "a", Pages: "2-4"}},
		"empty pages":       {{Name: "a", Pages: ""}},
		"too many groups":   make([]SplitGroup, MaxSplitGroups+1),
	}
	for name, groups := range tests {
		t.Run(name, func(t *testing.T) {
			_, err := service.Split(context.Background(), "input.pdf", t.TempDir(), groups)
			if !errors.Is(err, ErrInvalidInput) {
				t.Fatalf("Split() error = %v, want ErrInvalidInput", err)
			}
		})
	}
}

func TestSanitizeSplitBaseName(t *testing.T) {
	tests := map[string]string{
		`..\..\secret`:           "secret",
		"Rapport: été/2024?":     "Rapport_ été_2024",
		"CON":                    "_CON",
		"DMC-A-00-00.pdf":        "DMC-A-00-00",
		strings.Repeat("x", 200): strings.Repeat("x", maxSplitNameRunes),
		"...":                    "",
	}
	for input, want := range tests {
		if got := SanitizeSplitBaseName(input); got != want {
			t.Errorf("SanitizeSplitBaseName(%q) = %q, want %q", input, got, want)
		}
	}
}
