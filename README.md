<div align="center" markdown>
<img src="https://user-images.githubusercontent.com/106374579/182870013-5def504f-ba85-41b2-af88-bc9e3c9ca4e6.png"/>

# Videos project to images project

<p align="center">
  <a href="#Overview">Overview</a> •
  <a href="#How-To-Use">How To Use</a> •
  <a href="#Results">Results</a>
</p>


[![](https://img.shields.io/badge/supervisely-ecosystem-brightgreen)](https://ecosystem.supervisely.com/apps/turn-video-project-into-images)
[![](https://img.shields.io/badge/slack-chat-green.svg?logo=slack)](https://supervisely.com/slack)
![GitHub release (latest SemVer)](https://img.shields.io/github/v/release/supervisely-ecosystem/turn-video-project-into-images)
[![views](https://app.supervisely.com/img/badges/views/supervisely-ecosystem/turn-video-project-into-images.png)](https://supervisely.com)
[![runs](https://app.supervisely.com/img/badges/runs/supervisely-ecosystem/turn-video-project-into-images.png)](https://supervisely.com)

</div>

## Overview

Transforms supervisely **videos** project to supervisely **images** project. 

Application key points:  
- Backward compatible with [Images project to videos project](https://ecosystem.supervisely.com/apps/images-project-to-videos-project)
- Tag named `object_id` is used for backward compatibility with [Images project to videos project](https://ecosystem.supervisely.com/apps/images-project-to-videos-project)
- Dataset structure and names remain unchanged
- Result project name format: `"{original_project_name}(images)"`
- Image name format: `"{video_name}_frame_{:05d}.jpg", for example "my_video_frame_00077.jpg"`
- Video tags (both properties and frame range tags) are assigned to corresponding images and objects
- Information about original video project (`video_id`, `video_name`, `frame_index`, `video_dataset_id`, `video_dataset_name`, `video_project_id`, `video_project_name`) is assigned to every image as metadata. 


# How To Use 

1. Add [Videos project to images project](https://ecosystem.supervisely.com/apps/turn-video-project-into-images) to your team from Ecosystem.

<img data-key="sly-module-link" data-module-slug="supervisely-ecosystem/turn-video-project-into-images" src="https://i.imgur.com/9gUzdYM.png" width="350px" style='padding-bottom: 20px'/>  

2. Run app from the context menu of **Videos Project**:

<img src="https://i.imgur.com/rckw2ZP.png" width="100%"/>

3. Select whether you need all or only annotated video frames, select batch size, datasets and set frame step if needed. Press the `Run` button to launch.
 
<div align="center" markdown>
<img src="https://user-images.githubusercontent.com/48913536/187448689-15f050a4-6237-4d58-8c93-d0f34ff4ea13.png" width="500"/>
</div>


# Results

After running the application, you will be redirected to the `Tasks` page.  
Once application processing has finished, your project will be available.  
Click on the `project name` to proceed to it.

<img src="https://i.imgur.com/ADEnjJd.png"/>
