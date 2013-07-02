<?php
  header('Cache-Control: content=no-cache, no-store, must-revalidate');
  header('Pragma: content=no-cache');
  header('Expires: content=0');
  header('Content-type: application/json');
  
  $set = htmlspecialchars($_GET["set"]);
  $filename = "/mnt/p1tmpfs/data/$set.json";

  if (file_exists($filename)) {
  	  $data = file_get_contents($filename);
  	  echo $data;
  }
  else {
  	  echo "The file $filename does not exist";
  }  
?>
