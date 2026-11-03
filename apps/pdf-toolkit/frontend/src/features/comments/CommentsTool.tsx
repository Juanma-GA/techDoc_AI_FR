import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { ChevronLeft, ChevronRight, FileText, MessageSquare, Plus, Trash2, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button, Card, Input, Spinner, Textarea } from "@internal/ui";

import {
  chooseExportDestination,
  formatOperationError,
  processPDF,
  validateExportFileName,
  type ExportProgressState,
} from "../../shared/api";
import { FileDropzone } from "../../shared/components/FileDropzone";
import { formatFileSize } from "../../shared/files";
import { ExportProgress } from "../shared/ExportProgress";
import { CommentBoxControls } from "./CommentBoxControls";
import { CommentPagePreview } from "./CommentPagePreview";
import { centeredCommentBox, type CommentBox } from "./commentBox";
import { useCommentPdf } from "./useCommentPdf";
import "./comments.css";

type PDFComment = {
  id: number;
  page: number;
  box: CommentBox;
  content: string;
};

const maxComments = 100;
const maxCommentLength = 2000;

export function CommentsTool() {
  const { t, i18n } = useTranslation();
  const id = useId();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const nextCommentId = useRef(0);
  const [pageNumber, setPageNumber] = useState(1);
  const [comments, setComments] = useState<PDFComment[]>([]);
  const [draftPosition, setDraftPosition] = useState<{ page: number; box: CommentBox } | null>(null);
  const [draftContent, setDraftContent] = useState("");
  const [outputName, setOutputName] = useState("commented.pdf");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [working, setWorking] = useState(false);
  const [progress, setProgress] = useState<ExportProgressState>({
    phase: "uploading",
    percentage: 0,
  });
  const preview = useCommentPdf(file, pageNumber);
  const ready = Boolean(file) && preview.status === "ready";
  const language = i18n.resolvedLanguage ?? i18n.language ?? "fr";

  useEffect(() => {
    if (draftPosition) textareaRef.current?.focus();
  }, [draftPosition]);

  const createDraft = (box: CommentBox) => {
    if (!ready) return;
    if (comments.length >= maxComments) {
      setError(t("comments.maximumReached"));
      return;
    }
    setDraftPosition({ page: pageNumber, box });
    setDraftContent("");
    setError("");
  };

  const saveDraft = () => {
    const content = draftContent.trim();
    if (!draftPosition || !content) {
      setError(t("comments.contentRequired"));
      return;
    }
    if (comments.length >= maxComments) {
      setError(t("comments.maximumReached"));
      return;
    }
    setComments((current) => [
      ...current,
      { ...draftPosition, id: ++nextCommentId.current, content },
    ]);
    setDraftPosition(null);
    setDraftContent("");
    setError("");
    setSuccess(false);
  };

  const onFileSelected = (incoming: File[]) => {
    setFile(incoming[0] ?? null);
    setPageNumber(1);
    setComments([]);
    setDraftPosition(null);
    setDraftContent("");
    setError("");
    setSuccess(false);
  };

  const removeComment = (commentId: number) => {
    setComments((current) => current.filter((comment) => comment.id !== commentId));
    setSuccess(false);
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file || preview.status !== "ready" || comments.length === 0) {
      setError(t("comments.selectFileAndAdd"));
      return;
    }
    const filename = outputName.trim();
    const nameError = validateExportFileName(filename);
    if (nameError) {
      setError(t(`exportOptions.${nameError}`));
      return;
    }

    setWorking(true);
    setError("");
    setSuccess(false);
    setProgress({ phase: "uploading", percentage: 0 });
    try {
      const destinationChoice = await chooseExportDestination(filename, t);
      if (destinationChoice === null) return;
      const positionedComments = await Promise.all(comments.map(async (comment) => {
        const coordinates = await preview.convertBox(comment.page, comment.box);
        return { page: comment.page, ...coordinates, content: comment.content };
      }));
      const data = new FormData();
      data.append("file", file, file.name);
      data.append("comments", JSON.stringify(positionedComments));
      const savedName = await processPDF(
        "comments",
        data,
        filename,
        t,
        setProgress,
        destinationChoice,
      );
      setOutputName(savedName);
      setSuccess(true);
    } catch (reason: unknown) {
      setError(formatOperationError(reason, t, "errors.commentsFailed"));
    } finally {
      setWorking(false);
    }
  };

  const currentPageComments = comments.filter((comment) => comment.page === pageNumber);

  return (
    <form className="workflow-grid comments-workflow" onSubmit={submit}>
      <Card className="panel comments-preview-panel">
        <div className="panel-heading">
          <span className="step-number">01</span>
          <div>
            <h2>{t("comments.stepFile")}</h2>
            <p>{t("comments.stepFileDescription")}</p>
          </div>
        </div>
        <FileDropzone
          disabled={working}
          onFiles={onFileSelected}
          onError={setError}
        />
        {file ? (
          <div className="selected-file">
            <span className="file-row-icon"><FileText size={17} aria-hidden="true" /></span>
            <span className="file-details">
              <span className="file-name">{file.name}</span>
              <span className="file-size">{formatFileSize(file.size, language)}</span>
            </span>
            <Button
              type="button"
              variant="ghost"
              className="icon-button remove-button"
              disabled={working}
              aria-label={t("files.remove")}
              onClick={() => onFileSelected([])}
            >
              <X size={16} aria-hidden="true" />
            </Button>
          </div>
        ) : null}
        {preview.status === "loading" ? (
          <p className="preview-status" role="status">
            <Spinner aria-label={t("common.loading")} />{t("comments.previewLoading")}
          </p>
        ) : null}
        {preview.status === "failed" || preview.status === "no-pages" ? (
          <p className="feedback feedback-error" role="alert">{t("comments.previewFailed")}</p>
        ) : null}
        {preview.status === "empty" ? (
          <p className="thumbnail-empty">{t("comments.previewEmpty")}</p>
        ) : null}
        {file && preview.pageCount > 0 ? (
          <>
            <div
              className="comments-page-controls"
              role="group"
              aria-label={t("comments.pageNavigation")}
            >
              <Button
                type="button"
                variant="secondary"
                aria-label={t("comments.previousPage")}
                disabled={working || pageNumber <= 1}
                onClick={() => setPageNumber((current) => Math.max(1, current - 1))}
              >
                <ChevronLeft size={17} aria-hidden="true" />
              </Button>
              <label className="comments-page-label" htmlFor={`${id}-page`}>
                {t("comments.pageOf", { page: pageNumber, count: preview.pageCount })}
              </label>
              <Input
                id={`${id}-page`}
                type="number"
                min={1}
                max={preview.pageCount}
                value={pageNumber}
                disabled={working}
                className="comments-page-input"
                aria-label={t("comments.pageNumber")}
                onChange={(event) => {
                  const requested = Number(event.currentTarget.value);
                  if (Number.isInteger(requested)) {
                    setPageNumber(Math.min(preview.pageCount, Math.max(1, requested)));
                  }
                }}
              />
              <Button
                type="button"
                variant="secondary"
                aria-label={t("comments.nextPage")}
                disabled={working || pageNumber >= preview.pageCount}
                onClick={() => setPageNumber((current) => Math.min(preview.pageCount, current + 1))}
              >
                <ChevronRight size={17} aria-hidden="true" />
              </Button>
            </div>
            <p className="input-help">{t("comments.dragInstructions")}</p>
            <CommentPagePreview
              canvasRef={preview.canvasRef}
              pageNumber={pageNumber}
              pageSize={preview.pageSize}
              ready={ready}
              disabled={working}
              comments={currentPageComments}
              draftBox={draftPosition?.page === pageNumber ? draftPosition.box : null}
              onBoxSelected={createDraft}
            />
            <Button
              type="button"
              variant="secondary"
              className="comments-center-button"
              disabled={!ready || working || comments.length >= maxComments}
              onClick={() => createDraft(centeredCommentBox)}
            >
              <MessageSquare size={16} aria-hidden="true" />
              {t("comments.createCenterBox")}
            </Button>
          </>
        ) : null}
      </Card>

      <Card className="panel action-panel comments-action-panel">
        <div className="panel-heading">
          <span className="step-number">02</span>
          <div>
            <h2>{t("comments.stepComments", { count: comments.length })}</h2>
            <p>{t("comments.stepCommentsDescription")}</p>
          </div>
        </div>
        {draftPosition ? (
          <div className="comments-draft">
            <label className="field-label" htmlFor={`${id}-content`}>
              {t("comments.commentLabel", { page: draftPosition.page })}
            </label>
            <CommentBoxControls
              box={draftPosition.box}
              disabled={working}
              onChange={(box) => setDraftPosition((current) =>
                current ? { ...current, box } : current)}
            />
            <Textarea
              ref={textareaRef}
              id={`${id}-content`}
              maxLength={maxCommentLength}
              value={draftContent}
              disabled={working}
              aria-describedby={`${id}-content-help`}
              onChange={(event) => setDraftContent(event.currentTarget.value)}
            />
            <p className="input-help" id={`${id}-content-help`}>
              {t("comments.charactersRemaining", {
                count: maxCommentLength - draftContent.length,
              })}
            </p>
            <Button
              type="button"
              className="action-button"
              disabled={working || !draftContent.trim()}
              onClick={saveDraft}
            >
              <Plus size={17} aria-hidden="true" />
              {t("comments.addComment")}
            </Button>
          </div>
        ) : null}
        <div className="comments-list" aria-live="polite">
          {comments.length === 0 ? (
            <p className="thumbnail-empty">{t("comments.emptyList")}</p>
          ) : comments.map((comment) => (
            <div className="comments-list-item" key={comment.id}>
              <button
                type="button"
                className="comments-list-content"
                disabled={working}
                onClick={() => {
                  setPageNumber(comment.page);
                  setDraftPosition(null);
                }}
              >
                <span className="comments-list-page">{t("comments.pageShort", { page: comment.page })}</span>
                <span>{comment.content}</span>
              </button>
              <Button
                type="button"
                variant="ghost"
                className="icon-button"
                disabled={working}
                aria-label={t("comments.removeComment", { page: comment.page })}
                onClick={() => removeComment(comment.id)}
              >
                <Trash2 size={16} aria-hidden="true" />
              </Button>
            </div>
          ))}
        </div>
        <div className="comments-export">
          <label className="field-label" htmlFor={`${id}-output`}>
            {t("exportOptions.fileName")}
          </label>
          <Input
            id={`${id}-output`}
            value={outputName}
            disabled={working}
            aria-describedby={`${id}-output-help`}
            onChange={(event) => setOutputName(event.currentTarget.value)}
          />
          <p className="input-help" id={`${id}-output-help`}>
            {t("exportOptions.saveLocationHint")}
          </p>
          {working ? <ExportProgress progress={progress} /> : null}
          <Button
            type="submit"
            disabled={working || !ready || comments.length === 0}
            className="action-button"
          >
            {working ? <Spinner aria-label={t("common.loading")} /> : <MessageSquare size={18} />}
            {t(working ? "comments.working" : "comments.export")}
          </Button>
          <div className="feedback-slot">
            {error ? <p className="feedback feedback-error" role="alert">{error}</p> : null}
            {success ? (
              <p className="feedback feedback-success" role="status">
                {t("comments.success", { fileName: outputName })}
              </p>
            ) : null}
          </div>
        </div>
      </Card>
    </form>
  );
}
