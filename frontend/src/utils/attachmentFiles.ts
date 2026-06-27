const ACCEPTED_EXTENSIONS = ['.txt', '.md', '.pdf'];

function isAcceptedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
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
