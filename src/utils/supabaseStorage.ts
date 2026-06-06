import { createClient } from "@supabase/supabase-js";
import { config } from "../config";

const supabase = createClient(
  config.supabase.url!,
  config.supabase.key!
);

export const uploadToSupabase = async (
  file: Express.Multer.File,
  bucket: string = "food-images"
): Promise<string> => {
  try {
    const fileExt = file.originalname.split(".").pop();
    const fileName = `${Date.now()}-${Math.random().toString(36).substring(7)}.${fileExt}`;
    const filePath = `uploads/${fileName}`;

    const { data, error } = await supabase.storage
      .from(bucket)
      .upload(filePath, file.buffer, {
        contentType: file.mimetype,
        upsert: false,
      });

    if (error) {
      throw new Error(`Upload failed: ${error.message}`);
    }

    const { data: publicData } = supabase.storage
      .from(bucket)
      .getPublicUrl(filePath);

    return publicData.publicUrl;
  } catch (error: any) {
    console.error("❌ Supabase upload error:", error.message);
    throw error;
  }
};

export default supabase;
