package pdf

import (
	"context"
	"errors"
	"fmt"
	"os"
	"sort"
	"strconv"

	"github.com/pdfcpu/pdfcpu/pkg/api"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu/model"

	"pdf-toolkit/services"
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

func (p *PDFCPU) ImagesToPDF(ctx context.Context, inputFiles []string, output string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if err := api.ImportImagesFile(inputFiles, output, nil, model.NewDefaultConfiguration()); err != nil {
		return fmt.Errorf("pdfcpu import images: %w", err)
	}
	return ctx.Err()
}

func (p *PDFCPU) Compress(ctx context.Context, input, output string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if err := api.OptimizeFile(input, output, model.NewDefaultConfiguration()); err != nil {
		return fmt.Errorf("pdfcpu optimize: %w", err)
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

func (p *PDFCPU) OpenSplitDocument(ctx context.Context, input string) (services.SplitDocument, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	file, err := os.Open(input)
	if err != nil {
		return nil, fmt.Errorf("pdfcpu split open input: %w", err)
	}
	conf := model.NewDefaultConfiguration()
	conf.Cmd = model.TRIM
	source, err := api.ReadValidateAndOptimize(file, conf)
	if err != nil {
		return nil, errors.Join(fmt.Errorf("pdfcpu split read input: %w", err), file.Close())
	}
	if err := ctx.Err(); err != nil {
		return nil, errors.Join(err, file.Close())
	}
	return &pdfCPUSplitDocument{file: file, source: source}, nil
}

type pdfCPUSplitDocument struct {
	file   *os.File
	source *model.Context
}

func (d *pdfCPUSplitDocument) PageCount() int {
	return d.source.PageCount
}

func (d *pdfCPUSplitDocument) Extract(ctx context.Context, output string, pages []int) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if output == "" || len(pages) == 0 {
		return fmt.Errorf("pdfcpu split output and page selection are required")
	}
	selected := append([]int(nil), pages...)
	sort.Ints(selected)
	extracted, err := pdfcpu.ExtractPages(d.source, selected, false)
	if err != nil {
		return fmt.Errorf("pdfcpu split extract pages: %w", err)
	}
	file, err := os.OpenFile(output, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return fmt.Errorf("%w: create split output: %w", services.ErrOutputWrite, err)
	}
	writeErr := api.WriteContext(extracted, file)
	closeErr := file.Close()
	if err := errors.Join(writeErr, closeErr, ctx.Err()); err != nil {
		return errors.Join(
			fmt.Errorf("%w: write split output: %w", services.ErrOutputWrite, err),
			removeSplitOutput(output),
		)
	}
	return nil
}

func (d *pdfCPUSplitDocument) Close() error {
	return d.file.Close()
}

func removeSplitOutput(output string) error {
	if err := os.Remove(output); err != nil && !errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("remove incomplete split output: %w", err)
	}
	return nil
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

func (p *PDFCPU) Rotate(ctx context.Context, input, output string, pages []int, rotation int) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if err := api.RotateFile(input, output, rotation, pageSpecs(pages), model.NewDefaultConfiguration()); err != nil {
		return fmt.Errorf("pdfcpu rotate: %w", err)
	}
	return ctx.Err()
}

// Collect writes the given pages, in the given order, to output.
func (p *PDFCPU) Collect(ctx context.Context, input, output string, pages []int) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if len(pages) == 0 {
		return fmt.Errorf("pdfcpu collect: page list is required")
	}
	if err := api.CollectFile(input, output, pageSpecs(pages), model.NewDefaultConfiguration()); err != nil {
		return fmt.Errorf("pdfcpu collect: %w", err)
	}
	return ctx.Err()
}

func pageSpecs(pages []int) []string {
	if len(pages) == 0 {
		return nil
	}
	specs := make([]string, len(pages))
	for index, page := range pages {
		specs[index] = strconv.Itoa(page)
	}
	return specs
}
