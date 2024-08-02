import { Config } from "./src/config";

export const defaultConfig: Config = {
  url: "https://tommadness.github.io/KH2Randomizer",
  match: "https://tommadness.github.io/KH2Randomizer///**",
  maxPagesToCrawl: 1000,
  outputFileName: "../dynamic-files/kh2rando-website/kh2fmrando.json",
  maxTokens: 2000000,
};
