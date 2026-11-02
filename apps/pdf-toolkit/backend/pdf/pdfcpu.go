package pdf

import (
	"archive/zip"
	"context"
	"errors"
	"fmt"
	"io"
	"math"
	"os"
	"sort"
	"strconv"

	"github.com/pdfcpu/pdfcpu/pkg/api"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu/color"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu/model"
	"github.com/pdfcpu/pdfcpu/pkg/pdfcpu/types"

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

func (p *PDFCPU) ExtractImages(ctx context.Context, input, output string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	source, err := os.Open(input)
	if err != nil {
		return fmt.Errorf("pdfcpu extract images open input: %w", err)
	}
	archiveFile, err := os.OpenFile(output, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return errors.Join(
			fmt.Errorf("%w: create extracted image archive: %w", services.ErrOutputWrite, err),
			source.Close(),
		)
	}

	archive := zip.NewWriter(archiveFile)
	imageCount := 0
	extractErr := api.ExtractImages(source, nil, func(image model.Image, _ bool, _ int) error {
		if err := ctx.Err(); err != nil {
			return err
		}
		if image.Reader == nil {
			return fmt.Errorf("image object %d has no data", image.ObjNr)
		}
		extension, ok := extractedImageExtension(image.FileType)
		if !ok {
			return fmt.Errorf("image object %d has unsupported file type %q", image.ObjNr, image.FileType)
		}

		entryName := fmt.Sprintf("page-%04d-image-%04d.%s", image.PageNr, imageCount+1, extension)
		entry, err := archive.CreateHeader(&zip.FileHeader{Name: entryName, Method: zip.Store})
		if err != nil {
			return fmt.Errorf("%w: create image archive entry: %w", services.ErrOutputWrite, err)
		}
		if _, err := io.Copy(entry, image.Reader); err != nil {
			return fmt.Errorf("%w: write image archive entry: %w", services.ErrOutputWrite, err)
		}
		imageCount++
		return nil
	}, model.NewDefaultConfiguration())

	sourceCloseErr := source.Close()
	archiveCloseErr := archive.Close()
	outputCloseErr := archiveFile.Close()
	operationErr := errors.Join(extractErr, sourceCloseErr, archiveCloseErr, outputCloseErr, ctx.Err())
	if operationErr != nil {
		removeErr := removeExtractImagesOutput(output)
		if errors.Is(operationErr, context.Canceled) || errors.Is(operationErr, context.DeadlineExceeded) {
			return errors.Join(operationErr, removeErr)
		}
		if errors.Is(operationErr, services.ErrOutputWrite) || archiveCloseErr != nil || outputCloseErr != nil {
			return errors.Join(
				fmt.Errorf("%w: write extracted image archive: %w", services.ErrOutputWrite, operationErr),
				removeErr,
			)
		}
		return errors.Join(
			fmt.Errorf("%w: pdfcpu extract images: %w", services.ErrInvalidPDF, operationErr),
			removeErr,
		)
	}
	if imageCount == 0 {
		return errors.Join(services.ErrNoImages, removeExtractImagesOutput(output))
	}
	return nil
}

func extractedImageExtension(fileType string) (string, bool) {
	switch fileType {
	case "jpg", "png", "tif", "jpx", "jbig2":
		return fileType, true
	default:
		return "", false
	}
}

func removeExtractImagesOutput(output string) error {
	if err := os.Remove(output); err != nil && !errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("remove incomplete image archive: %w", err)
	}
	return nil
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

func (p *PDFCPU) Clean(ctx context.Context, input, output string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	file, err := os.Open(input)
	if err != nil {
		return fmt.Errorf("pdfcpu clean open input: %w", err)
	}
	conf := model.NewDefaultConfiguration()
	conf.Cmd = model.REMOVEANNOTATIONS
	document, err := api.ReadValidateAndOptimize(file, conf)
	closeErr := file.Close()
	if err != nil {
		return errors.Join(fmt.Errorf("pdfcpu clean read input: %w", err), closeErr)
	}
	if closeErr != nil {
		return fmt.Errorf("pdfcpu clean close input: %w", closeErr)
	}
	if err := ctx.Err(); err != nil {
		return err
	}
	if _, err := pdfcpu.RemoveAnnotations(document, nil, nil, nil, false); err != nil {
		return fmt.Errorf("pdfcpu clean remove annotations: %w", err)
	}
	if _, err := pdfcpu.PropertiesRemove(document, nil); err != nil {
		return fmt.Errorf("pdfcpu clean remove metadata: %w", err)
	}
	if document.Info != nil {
		if err := document.DeleteObjectGraph(*document.Info); err != nil {
			return fmt.Errorf("pdfcpu clean remove document info object: %w", err)
		}
		document.Info = nil
	}
	if err := ctx.Err(); err != nil {
		return err
	}

	file, err = os.OpenFile(output, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return fmt.Errorf("%w: pdfcpu clean create output: %w", services.ErrOutputWrite, err)
	}
	writeErr := api.WriteContext(document, file)
	closeErr = file.Close()
	if err := errors.Join(writeErr, closeErr, ctx.Err()); err != nil {
		return errors.Join(
			fmt.Errorf("%w: pdfcpu clean write output: %w", services.ErrOutputWrite, err),
			removeCleanOutput(output),
		)
	}
	return nil
}

func (p *PDFCPU) AddComments(
	ctx context.Context,
	input, output string,
	comments []services.PDFComment,
) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	annotations := make(map[int][]model.AnnotationRenderer, len(comments))
	for index, comment := range comments {
		rect := types.NewRectangle(
			math.Min(comment.X1, comment.X2),
			math.Min(comment.Y1, comment.Y2),
			math.Max(comment.X1, comment.X2),
			math.Max(comment.Y1, comment.Y2),
		)
		quad := types.QuadPoints{*types.NewQuadLiteralForRect(rect)}
		opacity := 0.35
		highlightColor := color.SimpleColor{R: 1, G: 0.9, B: 0}
		annotation := model.NewHighlightAnnotation(
			*rect,
			0,
			comment.Content,
			fmt.Sprintf("pdf-toolkit-comment-%d", index+1),
			"",
			0,
			&highlightColor,
			0,
			0,
			0,
			"",
			nil,
			&opacity,
			"",
			"Comment",
			quad,
		)
		annotations[comment.Page] = append(annotations[comment.Page], annotation)
	}
	if err := api.AddAnnotationsMapFile(
		input,
		output,
		annotations,
		model.NewDefaultConfiguration(),
		false,
	); err != nil {
		return fmt.Errorf("pdfcpu add comments: %w", err)
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

func removeCleanOutput(output string) error {
	if err := os.Remove(output); err != nil && !errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("remove incomplete cleaned PDF: %w", err)
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
