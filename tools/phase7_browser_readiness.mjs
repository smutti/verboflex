import {createRequire} from "node:module";
const require=createRequire(new URL("../frontend/package.json",import.meta.url));
const {expect}=require("@playwright/test");

export async function waitForSubmissionDetail(page) {
  await Promise.all(["Included proposals","File changes","Submitted values","Activity"].map(async name=>{
    const region=page.getByRole("region",{name,exact:true});
    await expect(region).toBeVisible();
    await expect(region.getByRole("status")).toHaveCount(0);
    await expect(region.getByRole("alert")).toHaveCount(0);
  }));
}
