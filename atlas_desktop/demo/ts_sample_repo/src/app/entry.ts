import { runTesting } from "@app/vs/workbench/contrib/testing/testingService";
import { helper } from "./lib/helper";

export const main = (): void => {
  runTesting();
  helper();
};
