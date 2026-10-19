package services

import (
	"fmt"
	"strconv"
	"strings"
)

func ParsePageSelection(selection string, pageCount int) ([]int, error) {
	if pageCount < 1 {
		return nil, fmt.Errorf("%w: PDF does not contain pages", ErrInvalidPDF)
	}

	selection = strings.TrimSpace(selection)
	if selection == "" {
		return nil, fmt.Errorf("%w: page selection is required", ErrInvalidInput)
	}

	terms := strings.Split(selection, ",")
	pages := make([]int, 0, len(terms))
	seen := make(map[int]struct{})

	for _, term := range terms {
		bounds := strings.Split(strings.TrimSpace(term), "-")
		if len(bounds) > 2 {
			return nil, fmt.Errorf("%w: invalid page range", ErrInvalidInput)
		}

		first, err := parsePageNumber(bounds[0])
		if err != nil {
			return nil, err
		}
		last := first
		if len(bounds) == 2 {
			last, err = parsePageNumber(bounds[1])
			if err != nil {
				return nil, err
			}
			if first > last {
				return nil, fmt.Errorf("%w: page ranges must be ascending", ErrInvalidInput)
			}
		}
		if last > pageCount {
			return nil, fmt.Errorf("%w: page number is outside the document", ErrInvalidInput)
		}

		for page := first; page <= last; page++ {
			if _, exists := seen[page]; exists {
				return nil, fmt.Errorf("%w: page numbers must not be repeated", ErrInvalidInput)
			}
			seen[page] = struct{}{}
			pages = append(pages, page)
		}
	}

	return pages, nil
}

func parsePageNumber(value string) (int, error) {
	value = strings.TrimSpace(value)
	if value == "" {
		return 0, fmt.Errorf("%w: invalid page number", ErrInvalidInput)
	}
	for _, digit := range value {
		if digit < '0' || digit > '9' {
			return 0, fmt.Errorf("%w: invalid page number", ErrInvalidInput)
		}
	}

	page, err := strconv.Atoi(value)
	if err != nil || page < 1 {
		return 0, fmt.Errorf("%w: page numbers start at 1", ErrInvalidInput)
	}
	return page, nil
}
