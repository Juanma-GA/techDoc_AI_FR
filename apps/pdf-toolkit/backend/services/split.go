package services

import (
	"context"
	"errors"
	"fmt"
	"os"
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
	return s.SplitWithProgress(ctx, input, outputDir, groups, nil)
}

func (s *PDFService) SplitWithProgress(
	ctx context.Context,
	input, outputDir string,
	groups []SplitGroup,
	onProgress func(completed, total int),
) (outputs []SplitOutput, err error) {
	return s.splitWithProgress(ctx, input, outputDir, groups, onProgress, false)
}

func (s *PDFService) SplitToDirectoryWithProgress(
	ctx context.Context,
	input, outputDir string,
	groups []SplitGroup,
	onProgress func(completed, total int),
) (outputs []SplitOutput, err error) {
	return s.splitWithProgress(ctx, input, outputDir, groups, onProgress, true)
}

func (s *PDFService) splitWithProgress(
	ctx context.Context,
	input, outputDir string,
	groups []SplitGroup,
	onProgress func(completed, total int),
	directOutput bool,
) (outputs []SplitOutput, err error) {
	if outputDir == "" {
		return nil, fmt.Errorf("%w: output directory is required", ErrInvalidInput)
	}
	if len(groups) == 0 || len(groups) > MaxSplitGroups {
		return nil, fmt.Errorf("%w: between 1 and %d documents are required", ErrInvalidInput, MaxSplitGroups)
	}
	if input == "" {
		return nil, fmt.Errorf("%w: input PDF is required", ErrInvalidInput)
	}
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	if directOutput {
		if _, ok := s.processor.(SplitDocumentProvider); !ok {
			return nil, fmt.Errorf("%w: direct split output is unavailable", ErrInvalidInput)
		}
		info, err := os.Stat(outputDir)
		if err != nil {
			return nil, fmt.Errorf("%w: inspect output directory: %w", ErrOutputWrite, err)
		}
		if !info.IsDir() {
			return nil, fmt.Errorf("%w: output path is not a directory", ErrInvalidInput)
		}
	}

	var createdPaths []string
	if directOutput {
		defer func() {
			if err == nil {
				return
			}
			for _, outputPath := range createdPaths {
				if removeErr := os.Remove(outputPath); removeErr != nil && !errors.Is(removeErr, os.ErrNotExist) {
					err = errors.Join(err, fmt.Errorf("remove partial split output %q: %w", outputPath, removeErr))
				}
			}
			outputs = nil
		}()
	}

	var pageCount int
	var document SplitDocument
	if provider, ok := s.processor.(SplitDocumentProvider); ok {
		document, err = provider.OpenSplitDocument(ctx, input)
		if err != nil {
			if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
				return nil, err
			}
			return nil, fmt.Errorf("%w: read page count: %w", ErrInvalidPDF, err)
		}
		if document == nil {
			return nil, fmt.Errorf("%w: split document provider returned no document", ErrInvalidPDF)
		}
		defer func() {
			if closeErr := document.Close(); closeErr != nil {
				err = errors.Join(err, fmt.Errorf("close split source: %w", closeErr))
				outputs = nil
			}
		}()
		pageCount = document.PageCount()
		if pageCount < 1 {
			return nil, fmt.Errorf("%w: PDF does not contain pages", ErrInvalidPDF)
		}
	} else {
		pageCount, err = s.pageCount(ctx, input)
		if err != nil {
			return nil, err
		}
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
	usedNames := make(map[string]struct{}, len(names))
	if directOutput {
		usedNames = make(map[string]struct{}, len(names))
		names, err = uniqueSplitFileNamesInDirectory(groups, outputDir, usedNames)
		if err != nil {
			return nil, fmt.Errorf("%w: choose split output names: %w", ErrOutputWrite, err)
		}
	}
	outputs = make([]SplitOutput, len(groups))
	if onProgress != nil {
		onProgress(0, len(groups))
	}
	for index, pages := range selections {
		if err := ctx.Err(); err != nil {
			return nil, err
		}
		output := filepath.Join(outputDir, fmt.Sprintf("part-%04d.pdf", index+1))
		if directOutput {
			output = filepath.Join(outputDir, names[index])
		}
		for {
			if document != nil {
				err = document.Extract(ctx, output, pages)
			} else {
				err = s.processor.Extract(ctx, input, output, pages)
			}
			if !directOutput || !errors.Is(err, os.ErrExist) {
				break
			}
			names[index], err = availableSplitFileName(outputDir, strings.TrimSuffix(names[index], ".pdf"), usedNames)
			if err != nil {
				return nil, fmt.Errorf("%w: choose split output name: %w", ErrOutputWrite, err)
			}
			output = filepath.Join(outputDir, names[index])
		}
		if err != nil {
			if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
				return nil, err
			}
			if errors.Is(err, ErrOutputWrite) {
				return nil, err
			}
			return nil, fmt.Errorf("%w: split pages: %w", ErrInvalidPDF, err)
		}
		outputs[index] = SplitOutput{Name: names[index], Path: output}
		if directOutput {
			createdPaths = append(createdPaths, output)
		}
		if onProgress != nil {
			onProgress(index+1, len(groups))
		}
	}
	return outputs, nil
}

func uniqueSplitFileNamesInDirectory(
	groups []SplitGroup,
	outputDir string,
	usedNames map[string]struct{},
) ([]string, error) {
	names := UniqueSplitFileNames(groups)
	for index, name := range names {
		availableName, err := availableSplitFileName(outputDir, strings.TrimSuffix(name, ".pdf"), usedNames)
		if err != nil {
			return nil, err
		}
		names[index] = availableName
	}
	return names, nil
}

func availableSplitFileName(outputDir, baseName string, usedNames map[string]struct{}) (string, error) {
	candidate := baseName
	for suffix := 2; ; suffix++ {
		name := candidate + ".pdf"
		key := strings.ToLower(name)
		if _, exists := usedNames[key]; exists {
			candidate = baseName + "_" + strconv.Itoa(suffix)
			continue
		}
		_, err := os.Lstat(filepath.Join(outputDir, name))
		if err == nil {
			candidate = baseName + "_" + strconv.Itoa(suffix)
			continue
		}
		if !errors.Is(err, os.ErrNotExist) {
			return "", err
		}
		usedNames[key] = struct{}{}
		return name, nil
	}
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
