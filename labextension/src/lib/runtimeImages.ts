// Copyright 2026 The Kubeflow Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import * as JSON5 from 'json5';

export type RuntimeImages = Record<string, string>;

export function getRuntimeImageName(
  runtimeImages: RuntimeImages,
  image: string,
): string | undefined {
  return Object.entries(runtimeImages).find(([, value]) => value === image)?.[0];
}

/** Repair a name written as an image tag by the old freeSolo blur behavior. */
export function repairRuntimeImageTag(
  tags: string[],
  runtimeImages: RuntimeImages,
): string[] | null {
  const index = tags.findIndex(tag => tag.startsWith('image:'));
  if (index === -1) {
    return null;
  }
  const image = tags[index].slice('image:'.length);
  if (
    Object.values(runtimeImages).includes(image) ||
    !Object.prototype.hasOwnProperty.call(runtimeImages, image) ||
    !runtimeImages[image] ||
    runtimeImages[image] === image
  ) {
    return null;
  }
  const repaired = [...tags];
  repaired[index] = `image:${runtimeImages[image]}`;
  return repaired;
}

/** Keep existing image references usable until users give them friendly names. */
export function migrateRuntimeImages(value: unknown): RuntimeImages | null {
  if (
    !Array.isArray(value) ||
    !value.every(image => typeof image === 'string')
  ) {
    return null;
  }
  const images: RuntimeImages = Object.create(null);
  value.forEach(image => {
    if (image) {
      images[image] = image;
    }
  });
  return images;
}

/** Rewrite legacy user settings before JupyterLab validates the new schema. */
export function migrateRuntimeImageSettingsRaw(
  raw: string,
): { raw: string; images: RuntimeImages } | null {
  const user = JSON5.parse(raw || '{}');
  const images = migrateRuntimeImages(user?.runtimeImages);
  if (images === null) {
    return null;
  }
  return {
    raw: JSON.stringify({ ...user, runtimeImages: images }, null, 2),
    images,
  };
}
