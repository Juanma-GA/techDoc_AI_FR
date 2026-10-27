package services

import (
	"context"
	"errors"
	"fmt"
	"path/filepath"
	"strconv"
	"strings"
	"unicode"
)

const (
	MaxSplitGroups       = 5000
	maxSplitNameRunes    = 150
	defaultSplitBaseName = "document"
)

// SplitGroup describes one output document: its requested file name and page selection.
type SplitGroup struct {
	Name  string `json:"name"`
	Pages string `json:"pages"`
}

// SplitOutput is a generated document stored inside the output directory.
type SplitOutput struct {
	Name string
	Path string
}

var windowsReservedNames = map[string]struct{}{
	"CON": {}, "PRN": {}, "AUX": {}, "NUL": {},
	"COM1": {}, "COM2": {}, "COM3": {}, "COM4": {}, "COM5": {}, "COM6": {}, "COM7": {}, "COM8": {}, "COM9": {},
	"LPT1": {}, "LPT2": {}, "LPT3": {}, "LPT4": {}, "LPT5": {}, "LPT6": {}, "LPT7": {}, "LPT8": {}, "LPT9": {},
}

// Split extracts every group into its own PDF inside outputDir and returns the generated files in order.
func (s *PDFService) Split(ctx context.Context, input, outputDir string, groups []SplitGroup) ([]SplitOutput, error) {
	if outputDir == "" {
		return nil, fmt.Errorf("%w: output directory is required", ErrInvalidInput)
	}
	if len(groups) == 0 || len(groups) > MaxSplitGroups {
		return nil, fmt.Errorf("%w: between 1 and %d documents are required", ErrInvalidInput, MaxSplitGroups)
	}
	pageCount, err := s.pageCount(ctx, input)
	if err != nil {
		return nil, err
	}

	selections := make([][]int, len(groups))
	for index, group := range groups {
		pages, err := ParsePageSelection(group.Pages, pageCount)
		if err != nil {
			return nil, fmt.Errorf("document %d: %w", index+1, err)
		}
		selections[index] = pages
	}

	names := UniqueSplitFileNames(groups)
	outputs := make([]SplitOutput, len(groups))
	for index, pages := range selections {
		if err := ctx.Err(); err != nil {
			return nil, err
		}
		output := filepath.Join(outputDir, fmt.Sprintf("part-%04d.pdf", index+1))
		if err := s.processor.Extract(ctx, input, output, pages); err != nil {
			if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
				return nil, err
			}
			return nil, fmt.Errorf("%w: split pages: %w", ErrInvalidPDF, err)
		}
		outputs[index] = SplitOutput{Name: names[index], Path: output}
	}
	return outputs, nil
}

// UniqueSplitFileNames sanitizes requested names and suffixes duplicates (case-insensitive) with _2, _3...
func UniqueSplitFileNames(groups []SplitGroup) []string {
	names := make([]string, len(groups))
	used := make(map[string]struct{}, len(groups))
	for index, group := range groups {
		base := SanitizeSplitBaseName(group.Name)
		if base == "" {
			base = fmt.Sprintf("%s-%d", defaultSplitBaseName, index+1)
		}
		candidate := base
		for suffix := 2; ; suffix++ {
			key := strings.ToLower(candidate)
			if _, exists := used[key]; !exists {
				used[key] = struct{}{}
				break
			}
			candidate = base + "_" + strconv.Itoa(suffix)
		}
		names[index] = candidate + ".pdf"
	}
	return names
}

// SanitizeSplitBaseName keeps a portable file name without extension, or returns "" when nothing usable remains.
func SanitizeSplitBaseName(name string) string {
	name = strings.TrimSpace(name)
	if strings.HasSuffix(strings.ToLower(name), ".pdf") {
		name = name[:len(name)-len(".pdf")]
	}

	var cleaned strings.Builder
	for _, character := range name {
		switch {
		case unicode.IsLetter(character), unicode.IsDigit(character):
			cleaned.WriteRune(character)
		case strings.ContainsRune(" -_.()[]+,&'#=@", character):
			cleaned.WriteRune(character)
		default:
			cleaned.WriteRune('_')
		}
	}

	result := strings.Trim(cleaned.String(), " ._")
	if runes := []rune(result); len(runes) > maxSplitNameRunes {
		result = strings.TrimRight(string(runes[:maxSplitNameRunes]), " ._")
	}
	if result == "" {
		return ""
	}
	stem := strings.ToUpper(strings.SplitN(result, ".", 2)[0])
	if _, reserved := windowsReservedNames[strings.TrimSpace(stem)]; reserved {
		result = "_" + result
	}
	return result
}
