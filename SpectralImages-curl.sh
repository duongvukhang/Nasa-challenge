#! /bin/sh
cat <<EOF
************************************************
*
*    Date: Thu Oct 22 11:36:26 PDT 2026
*
*    Script to download SPHEREx data from IRSA
*
*    The script below defines a subroutine to download the files
*
************************************************

EOF
    download_file() {

      href="$1"
      targetDir="$2"
      baseFileName="$3"
      suffix="$4"

      startDir=$(pwd)

      # create temp dir
      tmpDir=$(mktemp -d)
      cd "$tmpDir" || return 1

      echo ">> downloading ${href} ..."
      cmd="curl -fLJO"
      $cmd "$href" || {
        echo ">> ERROR: failed to download ${href}"
        cd "$startDir"
        rm -rf "$tmpDir"
        return 1
      }

      # get most recently modified file
      downloadedFile=$(ls -t | head -n 1)

      # determine filename
      if [ -n "$baseFileName" ]; then
        ext="${baseFileName##*.}"
        name="${baseFileName%.*}"
      else
        ext="${downloadedFile##*.}"
        name="${downloadedFile%.*}"
      fi

      # Apply suffix, if available
      finalName="$name"
      [ -n "$suffix" ] && finalName="${finalName}-$suffix"
      finalFile="${finalName}.${ext}"

      # create target dir in current directory
      if [ -n "$targetDir" ]; then
        destDir="$startDir/$targetDir"
      else
        destDir="$startDir"
      fi
      mkdir -p "$destDir"

      # resolve naming conflicts
      destPath="$destDir/$finalFile"
      count=1
      while [ -e "$destPath" ]; do
        destPath="$destDir/${finalName} (${count}).${ext}"
        count=$((count + 1))
      done

      # move file to main directory and cleanup
      mv "$downloadedFile" "$destPath"
      echo ">> Saved as $destPath"

      

      cd "$startDir"
      rm -rf "$tmpDir"
    }

download_file 'https://irsa.ipac.caltech.edu/ibe/data/spherex/qr2/level2/2025W28_1B/l2b-v20-2025-260/1/level2_2025W28_1B_0480_4D1_spx_l2b-v20-2025-260.fits' 'SPHERExLVFSurveyData' '' ''
