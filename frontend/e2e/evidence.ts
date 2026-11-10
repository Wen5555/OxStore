import fs from 'node:fs'
import path from 'node:path'
import type { Page } from '@playwright/test'

export function evidenceDir(...parts: string[]) {
  const root = process.env.OXSTORE_EVIDENCE_DIR
    ?? path.resolve(process.cwd(), '../docs/test/evidence/r2-personalized')
  const dir = path.join(root, ...parts)
  fs.mkdirSync(dir, { recursive: true })
  return dir
}

export async function saveShot(page: Page, group: string, name: string) {
  const dir = evidenceDir(group, 'screenshots')
  await page.screenshot({ path: path.join(dir, `${name}.png`), fullPage: true })
}
