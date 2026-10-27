// The little of gifenc (a GIF encoder with no types of its own) that
// tools/make_screenshots.ts uses.
declare module "gifenc" {
    type Palette = number[][];
    interface Encoder {
        writeFrame(
            index: Uint8Array,
            width: number,
            height: number,
            options?: {
                palette?: Palette;
                delay?: number;
                repeat?: number;
                transparent?: boolean;
                transparentIndex?: number;
                dispose?: number;
            },
        ): void;
        finish(): void;
        bytes(): Uint8Array;
    }
    const gifenc: {
        GIFEncoder(): Encoder;
        quantize(rgba: Uint8Array, maxColors: number, options?: { format?: string }): Palette;
        applyPalette(rgba: Uint8Array, palette: Palette, format?: string): Uint8Array;
    };
    export default gifenc;
}
