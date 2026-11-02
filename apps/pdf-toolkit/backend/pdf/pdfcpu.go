package pdf

import (
	"archive/zip"
	"context"
	"crypto/sha256"
	"errors"
	"fmt"
	"io"
	"math"
	"os"
	"path"
	"path/filepath"
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

type extractedImageFile struct {
	name        string
	path        string
	contentHash [sha256.Size]byte
}

func (p *PDFCPU) ExtractImages(ctx context.Context, input, output string) (returnErr error) {
	if err := ctx.Err(); err != nil {
		return err
	}
	source, err := os.Open(input)
	if err != nil {
		return fmt.Errorf("pdfcpu extract images open input: %w", err)
	}
	stagingDir, err := os.MkdirTemp(filepath.Dir(output), ".pdf-toolkit-images-")
	if err != nil {
		return errors.Join(
			fmt.Errorf("%w: create image staging directory: %w", services.ErrOutputWrite, err),
			source.Close(),
		)
	}
	defer func() {
		if err := os.RemoveAll(stagingDir); err != nil {
			returnErr = errors.Join(returnErr, fmt.Errorf("remove image staging directory: %w", err))
		}
	}()

	var images []extractedImageFile
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

		entryName := fmt.Sprintf("page-%04d-image-%04d.%s", image.PageNr, len(images)+1, extension)
		stagedPath := filepath.Join(stagingDir, entryName)
		stagedFile, err := os.OpenFile(stagedPath, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
		if err != nil {
			return fmt.Errorf("%w: create staged image: %w", services.ErrOutputWrite, err)
		}
		contentHasher := sha256.New()
		_, copyErr := io.Copy(io.MultiWriter(stagedFile, contentHasher), image.Reader)
		closeErr := stagedFile.Close()
		if copyErr != nil || closeErr != nil {
			return fmt.Errorf(
				"%w: write staged image: %w",
				services.ErrOutputWrite,
				errors.Join(copyErr, closeErr),
			)
		}
		if err := ctx.Err(); err != nil {
			return err
		}
		var contentHash [sha256.Size]byte
		copy(contentHash[:], contentHasher.Sum(nil))
		images = append(images, extractedImageFile{
			name:        entryName,
			path:        stagedPath,
			contentHash: contentHash,
		})
		return nil
	}, model.NewDefaultConfiguration())

	sourceCloseErr := source.Close()
	operationErr := errors.Join(extractErr, sourceCloseErr, ctx.Err())
	if operationErr != nil {
		if errors.Is(operationErr, context.Canceled) || errors.Is(operationErr, context.DeadlineExceeded) {
			return operationErr
		}
		if errors.Is(operationErr, services.ErrOutputWrite) {
			return fmt.Errorf("%w: stage extracted images: %w", services.ErrOutputWrite, operationErr)
		}
		return fmt.Errorf("%w: pdfcpu extract images: %w", services.ErrInvalidPDF, operationErr)
	}
	if len(images) == 0 {
		return services.ErrNoImages
	}

	archiveFile, err := os.OpenFile(output, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return fmt.Errorf("%w: create extracted image archive: %w", services.ErrOutputWrite, err)
	}
	archive := zip.NewWriter(archiveFile)
	archiveErr := writeExtractedImageArchive(ctx, archive, images)
	archiveCloseErr := archive.Close()
	outputCloseErr := archiveFile.Close()
	operationErr = errors.Join(archiveErr, archiveCloseErr, outputCloseErr, ctx.Err())
	if operationErr != nil {
		removeErr := removeExtractImagesOutput(output)
		if errors.Is(operationErr, context.Canceled) || errors.Is(operationErr, context.DeadlineExceeded) {
			return errors.Join(operationErr, removeErr)
		}
		return errors.Join(
			fmt.Errorf("%w: write extracted image archive: %w", services.ErrOutputWrite, operationErr),
			removeErr,
		)
	}
	return nil
}

func writeExtractedImageArchive(
	ctx context.Context,
	archive *zip.Writer,
	images []extractedImageFile,
) error {
	occurrences := make(map[[sha256.Size]byte]int, len(images))
	for _, image := range images {
		occurrences[image.contentHash]++
	}

	folders := make(map[[sha256.Size]byte]string)
	groupNumber := 0
	for _, image := range images {
		if err := ctx.Err(); err != nil {
			return err
		}
		entryName := image.name
		if occurrences[image.contentHash] > 2 {
			folder, ok := folders[image.contentHash]
			if !ok {
				groupNumber++
				folder = fmt.Sprintf("images_recurrentes/groupe-%03d", groupNumber)
				folders[image.contentHash] = folder
			}
			entryName = path.Join(folder, image.name)
		}

		entry, err := archive.CreateHeader(&zip.FileHeader{Name: entryName, Method: zip.Store})
		if err != nil {
			return fmt.Errorf("%w: create image archive entry: %w", services.ErrOutputWrite, err)
		}
		stagedFile, err := os.Open(image.path)
		if err != nil {
			return fmt.Errorf("%w: open staged image: %w", services.ErrOutputWrite, err)
		}
		_, copyErr := io.Copy(entry, stagedFile)
		closeErr := stagedFile.Close()
		if copyErr != nil || closeErr != nil {
			return fmt.Errorf(
				"%w: write image archive entry: %w",
				services.ErrOutputWrite,
				errors.Join(copyErr, closeErr),
			)
		}
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
