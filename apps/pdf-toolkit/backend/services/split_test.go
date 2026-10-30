package services

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

type splitProcessor struct {
	fakeProcessor
	extracted [][]int
}

type splitDocumentTestProcessor struct {
	*splitProcessor
	openCalls      int
	pageCountCalls int
	document       *splitDocumentTestDocument
}

type splitDocumentTestDocument struct {
	pageCount     int
	extracted     [][]int
	closed        bool
	extractCalls  int
	failOnExtract int
}

func (p *splitProcessor) Extract(_ context.Context, _, _ string, pages []int) error {
	p.extracted = append(p.extracted, append([]int(nil), pages...))
	return nil
}

func (p *splitDocumentTestProcessor) PageCount(ctx context.Context, input string) (int, error) {
	p.pageCountCalls++
	return p.splitProcessor.PageCount(ctx, input)
}

func (p *splitDocumentTestProcessor) OpenSplitDocument(context.Context, string) (SplitDocument, error) {
	p.openCalls++
	return p.document, nil
}

func (d *splitDocumentTestDocument) PageCount() int {
	return d.pageCount
}

func (d *splitDocumentTestDocument) Extract(ctx context.Context, output string, pages []int) error {
	d.extractCalls++
	if d.extractCalls == d.failOnExtract {
		return errors.New("injected extraction failure")
	}
	if err := os.WriteFile(output, []byte("%PDF-1.7\nprocessed"), 0o600); err != nil {
		return err
	}
	d.extracted = append(d.extracted, append([]int(nil), pages...))
	return ctx.Err()
}

func (d *splitDocumentTestDocument) Close() error {
	d.closed = true
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

func TestSplitReportsProgressAfterEachOutput(t *testing.T) {
	service := NewPDFService(&splitProcessor{fakeProcessor: fakeProcessor{pageCount: 3}})
	var completed []int
	var totals []int
	_, err := service.SplitWithProgress(context.Background(), "input.pdf", t.TempDir(), []SplitGroup{
		{Name: "one", Pages: "1"},
		{Name: "two", Pages: "2"},
		{Name: "three", Pages: "3"},
	}, func(done, total int) {
		completed = append(completed, done)
		totals = append(totals, total)
	})
	if err != nil {
		t.Fatalf("SplitWithProgress() error = %v", err)
	}
	if !reflect.DeepEqual(completed, []int{0, 1, 2, 3}) {
		t.Fatalf("progress completed = %v, want [0 1 2 3]", completed)
	}
	if !reflect.DeepEqual(totals, []int{3, 3, 3, 3}) {
		t.Fatalf("progress totals = %v, want [3 3 3 3]", totals)
	}
}

func TestSplitReusesSplitDocumentProvider(t *testing.T) {
	document := &splitDocumentTestDocument{pageCount: 3}
	processor := &splitDocumentTestProcessor{
		splitProcessor: &splitProcessor{fakeProcessor: fakeProcessor{pageCount: 3}},
		document:       document,
	}
	outputs, err := NewPDFService(processor).Split(context.Background(), "input.pdf", t.TempDir(), []SplitGroup{
		{Name: "first", Pages: "1,3"},
		{Name: "second", Pages: "2"},
	})
	if err != nil {
		t.Fatalf("Split() error = %v", err)
	}
	if processor.openCalls != 1 || processor.pageCountCalls != 0 {
		t.Fatalf("split document opens = %d, page count calls = %d; want 1 open and no separate page count", processor.openCalls, processor.pageCountCalls)
	}
	if !document.closed {
		t.Fatal("split document was not closed")
	}
	if len(outputs) != 2 || !reflect.DeepEqual(document.extracted, [][]int{{1, 3}, {2}}) {
		t.Fatalf("outputs = %d, extracted = %v", len(outputs), document.extracted)
	}
}

func TestSplitToDirectoryAddsSuffixForExistingNames(t *testing.T) {
	outputDir := t.TempDir()
	existing := filepath.Join(outputDir, "DOC_A.pdf")
	if err := os.WriteFile(existing, []byte("keep"), 0o600); err != nil {
		t.Fatal(err)
	}
	document := &splitDocumentTestDocument{pageCount: 2}
	processor := &splitDocumentTestProcessor{
		splitProcessor: &splitProcessor{fakeProcessor: fakeProcessor{pageCount: 2}},
		document:       document,
	}

	outputs, err := NewPDFService(processor).SplitToDirectoryWithProgress(context.Background(), "input.pdf", outputDir, []SplitGroup{
		{Name: "DOC_A", Pages: "1"},
		{Name: "DOC_B", Pages: "2"},
	}, nil)
	if err != nil {
		t.Fatalf("SplitToDirectoryWithProgress() error = %v", err)
	}
	if got, want := []string{outputs[0].Name, outputs[1].Name}, []string{"DOC_A_2.pdf", "DOC_B.pdf"}; !reflect.DeepEqual(got, want) {
		t.Fatalf("output names = %v, want %v", got, want)
	}
	if content, err := os.ReadFile(existing); err != nil || string(content) != "keep" {
		t.Fatalf("existing output = %q, err = %v; existing file must not be overwritten", content, err)
	}
	for _, output := range outputs {
		if _, err := os.Stat(output.Path); err != nil {
			t.Fatalf("direct output %q is missing: %v", output.Path, err)
		}
	}
}

func TestSplitToDirectoryCleansCreatedFilesOnFailure(t *testing.T) {
	outputDir := t.TempDir()
	document := &splitDocumentTestDocument{pageCount: 2, failOnExtract: 2}
	processor := &splitDocumentTestProcessor{
		splitProcessor: &splitProcessor{fakeProcessor: fakeProcessor{pageCount: 2}},
		document:       document,
	}

	_, err := NewPDFService(processor).SplitToDirectoryWithProgress(context.Background(), "input.pdf", outputDir, []SplitGroup{
		{Name: "DOC_A", Pages: "1"},
		{Name: "DOC_B", Pages: "2"},
	}, nil)
	if err == nil {
		t.Fatal("SplitToDirectoryWithProgress() error = nil, want extraction failure")
	}
	entries, err := os.ReadDir(outputDir)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 0 {
		t.Fatalf("leftover direct outputs after failure: %v", entries)
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
