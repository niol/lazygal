<!DOCTYPE html
     PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
     "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
  <title>%(dir)s - %(image_name)s</title>
  <meta http-equiv="content-type" content="text/html; charset=utf-8" />
  <link rel="alternate stylesheet" type="text/css" media="screen,projection" title="Original" href="%(rel_root)sshared/style.css" />
</head>

<body>

<p><a href="index.html">Gallery index</a></p>

%(prev_link)s

%(next_link)s

<div id="image">
  <div id="image_img">
    <p><img src="%(img_src)s" width="%(img_width)s" height="%(img_height)s" alt="Image %(image_name)s" /></p>
  </div>
  <div id="image_caption">
    <ul>
       <li>%(image_name)s</li>
       <li>Taken %(image_date)s</li>
    </ul>
  </div>
</div>

</body>
</html>
