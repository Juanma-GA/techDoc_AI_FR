package pdf

import (
	"context"
	"fmt"
	"strconv"

	"github.com/pdfcpu/pdfcpu/pkg/api"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu/model"
)

type PDFCPU struct{}

func NewPDFCPU() *PDFCPU {
	return &PDFCPU{}
}

func (p *PDFCPU) Merge(ctx context.Context, inputFiles []string, output string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if err := api.MergeCreateFile(inputFiles, output, false, model.NewDefaultConfiguration()); err != nil {
		return fmt.Errorf("pdfcpu merge: %w", err)
	}
	return ctx.Err()
}

func (p *PDFCPU) PageCount(ctx context.Context, input string) (int, error) {
	if err := ctx.Err(); err != nil {
		return 0, err
	}
	pageCount, err := api.PageCountFile(input)
	if err != nil {
		return 0, fmt.Errorf("pdfcpu page count: %w", err)
	}
	if err := ctx.Err(); err != nil {
		return 0, err
	}
	return pageCount, nil
}

func (p *PDFCPU) Extract(ctx context.Context, input, output string, pages []int) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if err := api.TrimFile(input, output, pageSpecs(pages), model.NewDefaultConfiguration()); err != nil {
		return fmt.Errorf("pdfcpu extract: %w", err)
	}
	return ctx.Err()
}

func (p *PDFCPU) Delete(ctx context.Context, input, output string, pages []int) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if err := api.RemovePagesFile(input, output, pageSpecs(pages), model.NewDefaultConfiguration()); err != nil {
		return fmt.Errorf("pdfcpu delete: %w", err)
	}
	return ctx.Err()
}

func (p *PDFCPU) Reorder(ctx context.Context, input, output string, pages []int) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if err := api.CollectFile(input, output, pageSpecs(pages), model.NewDefaultConfiguration()); err != nil {
		return fmt.Errorf("pdfcpu reorder: %w", err)
	}
	return ctx.Err()
}

func pageSpecs(pages []int) []string {
	specs := make([]string, len(pages))
	for index, page := range pages {
		specs[index] = strconv.Itoa(page)
	}
	return specs
}
