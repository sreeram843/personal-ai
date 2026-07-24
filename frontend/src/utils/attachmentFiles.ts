const ACCEPTED_EXTENSIONS = ['.txt', '.md', '.pdf'];
/**
 * Client-side guard for the raw file size; server enforces INGEST_MAX_UPLOAD_BYTES
 * on the same raw bytes (PDFs carry fonts/images, so this is larger than the
 * extracted-text ceiling, INGEST_MAX_DOCUMENT_BYTES, which is checked server-side
 * after text extraction).
 */
export const MAX_UPLOAD_BYTES = 10_000_000;

function isAcceptedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

export function assertUploadAllowed(file: File): void {
  if (!isAcceptedFile(file)) {
    throw new Error(`Unsupported file type: ${file.name}. Use .txt, .md, or .pdf.`);
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    throw new Error(
      `${file.name} is too large (${file.size} bytes). Limit is ${MAX_UPLOAD_BYTES} bytes.`,
    );
  }
}

export function extractPastedFiles(event: { clipboardData: DataTransfer | null | undefined }): File[] {
  const items = event.clipboardData?.items;
  if (!items?.length) {
    return [];
  }
  const files: File[] = [];
  for (const item of items) {
    if (item.kind !== 'file') {
      continue;
    }
    const file = item.getAsFile();
    if (file && isAcceptedFile(file)) {
      files.push(file);
    }
  }
  return files;
}

export { ACCEPTED_EXTENSIONS, isAcceptedFile };
