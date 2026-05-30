import React from 'react';
import Root from '@theme-original/Root';
import StructuredData from '@site/src/components/StructuredData';

export default function RootWrapper(props) {
  return (
    <>
      <StructuredData />
      <Root {...props} />
    </>
  );
}
