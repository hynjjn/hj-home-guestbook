/** 업로드 전에 canvas로 미리 줄인다. 선택 사항이고, 줄였더라도 서버 재인코딩은 건너뛰지 않는다. */

const MAX_EDGE = 1600;

export async function shrink(file: File): Promise<File> {
  if (!("createImageBitmap" in window)) return file;

  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, MAX_EDGE / Math.max(bitmap.width, bitmap.height));
    if (scale === 1) {
      bitmap.close();
      return file;
    }

    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);

    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/webp", 0.85),
    );
    if (!blob || blob.size >= file.size) return file;

    return new File([blob], "photo.webp", { type: "image/webp" });
  } catch {
    return file; // 줄이기에 실패해도 원본을 그대로 보낸다
  }
}
