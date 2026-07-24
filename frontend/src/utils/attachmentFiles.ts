const ACCEPTED_EXTENSIONS = ['.txt', '.md', '.pdf'];
/** Client-side guard; server enforces INGEST_MAX_DOCUMENT_BYTES. */
export const MAX_UPLOAD_BYTES = 512_000;

function isAcceptedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

export function assertUploadAllowed(file: File): void {
  if (!isAcceptedFile(file)) {
    throw new Error(`Unsupported file type: ${file.name}. Use .txt or .md.`);
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
