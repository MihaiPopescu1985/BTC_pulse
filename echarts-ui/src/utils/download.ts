export const downloadDataUrl = (filename: string, dataUrl: string): void => {
  const anchor = document.createElement('a');
  anchor.href = dataUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
};

export const downloadTextFile = (filename: string, text: string, mimeType = 'application/json;charset=utf-8'): void => {
  const blob = new Blob([text], { type: mimeType });
  const objectUrl = URL.createObjectURL(blob);

  try {
    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
};

export const copyTextToClipboard = async (text: string): Promise<boolean> => {
  try {
    if (!navigator.clipboard) {
      return false;
    }

    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
};
