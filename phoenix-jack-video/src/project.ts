import {makeProject} from '@canvas-commons/core';

import intro from './scenes/01_intro?scene';
import round1 from './scenes/02_round1?scene';
import frameoff from './scenes/03_frameoff?scene';
import lightning from './scenes/04_lightning?scene';
import finalVote from './scenes/05_finalvote?scene';
import outro from './scenes/06_outro?scene';

export default makeProject({
  // Plays back-to-back. Total runtime ~90s @ default 1920x1080.
  scenes: [intro, round1, frameoff, lightning, finalVote, outro],
});
